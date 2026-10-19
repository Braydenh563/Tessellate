// search-suggest.js: every search box suggests as you type (the owner,
// 2026-10-11: "should searches suggest auto completions??"; SESSION_BRIEFS
// Brief 86, CHAT_PLAN decision 69). Loaded on the first focus of a box that
// carries `data-search-scope` (app.js `LAZY_MODULES.searchSuggest`).
//
// What it offers, in this order: the searches the person ran in this family of
// boxes (prefs.js `searchRecent`), then the titles, tags and categories of
// their own notes that start with the words typed. All of it is computed here
// from what the page already holds (`allEntries`), nothing is fetched and no
// model is asked, so it is as private as the search itself.
//
// How it is drawn: the rich picker's row (DESIGN.md, "a suggest list") in a
// listbox under the box, and the best completion as grey ghost text after the
// caret. The field keeps the focus throughout (a combobox): Down and Up move
// the lit row, Enter takes a lit row (an untouched list leaves Enter to the
// box), Tab or Right at the end of the text takes the ghost text, Escape
// closes the list first, Shift+Delete removes a lit recent search. A recent
// search also carries its own x and the list's foot a "Clear recent searches".
//
// Scopes (the `data-search-scope` of each box): "notes" boxes share their
// recents and complete from notes; every other scope keeps its own recents and
// completes from the titles of its own list (`SEARCH_SUGGEST_LISTS`). "web" is the web panel, whose own
// search records its recents once a search has answered.

//: **Recent searches, one store for every search box** (the owner, 2026-10-11:
//: "should the user be able to clear their ... recent searches in individual and
//: all places"). A scope is a family of boxes that share what was searched (the
//: notes boxes share one list, the web panel its own, each Library list its
//: own), kept on this device under `searchRecent:<scope>`. The web panel keeps
//: the key it always had (chat.js still writes it after a search, so the panel
//: needs nothing from this file to show its list). The "every box at once"
//: helpers are settings-data.js's.
const SEARCH_RECENT_MAX = 8;
const SEARCH_RECENT_PREFIX = "searchRecent:";
const searchRecent = {
  key: (scope) => (scope === "web" ? "webSearchHistory" : SEARCH_RECENT_PREFIX + scope),
  load: (scope) => prefs.json(searchRecent.key(scope), []).filter((q) => typeof q === "string" && q.trim()),
  //: Newest first, no duplicates (case aside), two letters at least.
  push(scope, query) {
    const text = String(query || "").trim().replace(/\s+/g, " ");
    if (text.length > 1) prefs.setJSON(searchRecent.key(scope), [text, ...searchRecent.load(scope).filter((q) => q.toLowerCase() !== text.toLowerCase())].slice(0, SEARCH_RECENT_MAX));
  },
  remove(scope, query) {
    prefs.setJSON(searchRecent.key(scope), searchRecent.load(scope).filter((q) => q.toLowerCase() !== String(query).toLowerCase()));
  },
  clear: (scope) => prefs.remove(searchRecent.key(scope)),
};

const SEARCH_SUGGEST_LIMITS = { recent: 4, title: 4, tag: 3, category: 2 };
const SEARCH_SUGGEST_PREF = "searchSuggest";

let searchSuggest = null;
//: The pool of note words, rebuilt when the list of notes changes.
const searchSuggestCache = { poolFor: null, pool: { titles: [], tags: new Map(), categories: new Map() }, measure: null };

function searchSuggestEnabled() {
  return prefs.get(SEARCH_SUGGEST_PREF, "on") !== "off";
}

function searchSuggestScopeOf(input) {
  return input?.dataset?.searchScope || "";
}

//: Titles, tags and categories of the notes in view: not the bin, not the
//: archive, not a private note (they are kept out of search on purpose).
function searchSuggestWords() {
  const entries = typeof allEntries !== "undefined" && Array.isArray(allEntries) ? allEntries : [];
  if (searchSuggestCache.poolFor === entries && searchSuggestCache.pool.size === entries.length) return searchSuggestCache.pool;
  const titles = [];
  const tags = new Map();
  const categories = new Map();
  for (const entry of entries) {
    if (!entry || entry.is_private || entry.deleted_at || entry.archived_at) continue;
    if (entry.title) titles.push(String(entry.title).trim());
    for (const tag of entry.tags || []) tags.set(tag, (tags.get(tag) || 0) + 1);
    if (entry.category) categories.set(entry.category, (categories.get(entry.category) || 0) + 1);
  }
  searchSuggestCache.pool = { titles: [...new Set(titles.filter(Boolean))], tags, categories, size: entries.length };
  searchSuggestCache.poolFor = entries;
  return searchSuggestCache.pool;
}

//: Starts with the words (rank 0), or has a word that does (rank 1), or not (-1).
function searchSuggestRank(label, query) {
  const text = label.toLowerCase();
  if (text.startsWith(query)) return 0;
  return (` ${text}`).replace(/[^a-z0-9À-￿]+/g, " ").includes(` ${query}`) ? 1 : -1;
}

//: The last word of the box and what stands before it, with the operator the
//: Notes filter reads (`#tag`, `tag:`, `cat:`) split off so a completion keeps it.
function searchSuggestToken(value) {
  const cut = value.search(/\S+$/);
  const head = cut === -1 ? value : value.slice(0, cut);
  const word = cut === -1 ? "" : value.slice(cut);
  const op = /^(#|tag:|cat:|category:)/i.exec(word);
  return { head, word, op: op ? op[1] : "", bare: op ? word.slice(op[1].length).replace(/^"/, "") : word };
}

//: A Library list's own titles (OPEN row 552: its box suggested recents only):
//: read from the rows drawn under the box, plus every title seen there before,
//: so a list already narrowed by the box still completes a shorter word.
const SEARCH_SUGGEST_LISTS = {
  documents: "#library-docs-list .doc-list-title",
  boards: "#library-boards-grid .library-card-title",
  library: "#library-grid .library-card-title",
  bookmarks: "#bookmark-list .bookmark-title",
  recordings: "#recordings-list .recording-title",
  skills: "#library-skills-section .skill-card-title",
};
const SEARCH_SUGGEST_ABOUT = { documents: "Document", boards: "Board", library: "Library item", bookmarks: "Bookmark", recordings: "Recording", skills: "Skill", images: "File" };
const searchSuggestSeenTitles = new Map();

function searchSuggestListTitles(scope) {
  const seen = searchSuggestSeenTitles.get(scope) || new Set();
  const selector = SEARCH_SUGGEST_LISTS[scope];
  const drawn = selector ? [...document.querySelectorAll(selector)].map((el) => el.textContent) : [];
  //: Images and files keep their names in the page's cache, not in a title row.
  if (scope === "images" && typeof libraryImagesCache !== "undefined") drawn.push(...libraryImagesCache.map((i) => i.original_name || ""));
  for (const text of drawn) {
    const title = String(text || "").trim();
    if (title && title !== "Untitled") seen.add(title);
  }
  searchSuggestSeenTitles.set(scope, seen);
  return [...seen];
}

//: Titles that start with the box's text (or have a word that does), best first.
function searchSuggestTitleHits(titles, query, seen) {
  return titles
    .map((title) => ({ title, rank: searchSuggestRank(title, query) }))
    .filter((hit) => hit.rank >= 0 && !seen.has(hit.title.toLowerCase()))
    .sort((a, b) => a.rank - b.rank || a.title.localeCompare(b.title))
    .slice(0, SEARCH_SUGGEST_LIMITS.title)
    .map((hit) => hit.title);
}

//: The suggestions for what is in the box now: [{kind, label, value, about}].
function searchSuggestItems(input) {
  const scope = searchSuggestScopeOf(input);
  const value = input.value;
  const query = value.trim().toLowerCase();
  const items = [];
  const seen = new Set([query]);
  //: The web panel already lists its recents under an empty box.
  if (!query && scope === "web") return items;
  const recents = searchRecent.load(scope);
  for (const text of recents) {
    const lower = text.toLowerCase();
    if (seen.has(lower) && query) continue;
    if (query && !lower.startsWith(query)) continue;
    items.push({ kind: "recent", label: text, value: text, about: "Recent search" });
    if (items.length >= (query ? SEARCH_SUGGEST_LIMITS.recent : 5)) break;
  }
  if (query && scope !== "notes") {
    for (const item of items) seen.add(item.value.toLowerCase());
    for (const title of searchSuggestTitleHits(searchSuggestListTitles(scope), query, seen)) {
      items.push({ kind: "item", label: title, value: title, about: SEARCH_SUGGEST_ABOUT[scope] || "Item" });
    }
  }
  if (!query || scope !== "notes") return items;
  for (const item of items) seen.add(item.value.toLowerCase());
  const words = searchSuggestWords();
  const { head, word, op, bare } = searchSuggestToken(value);
  const wanted = bare.toLowerCase();
  const wholeSingle = !/\s/.test(query);
  //: Titles complete the whole box; a typed operator means a tag or category was meant.
  if (!op) {
    const titled = words.titles
      .map((title) => ({ title, rank: searchSuggestRank(title, query) }))
      .filter((hit) => hit.rank >= 0 && !seen.has(hit.title.toLowerCase()))
      .sort((a, b) => a.rank - b.rank)
      .slice(0, SEARCH_SUGGEST_LIMITS.title);
    for (const { title } of titled) {
      items.push({ kind: "title", label: title, value: title, about: "Note" });
      seen.add(title.toLowerCase());
    }
  }
  const wantsTags = !op || op === "#" || /^tag:/i.test(op);
  const wantsCategories = !op || /^(cat|category):/i.test(op);
  if (wantsTags && wanted && (wholeSingle || op || word)) {
    const hits = [...words.tags.entries()]
      .filter(([tag]) => searchSuggestRank(tag, wanted) >= 0 && tag.toLowerCase() !== wanted)
      .sort((a, b) => searchSuggestRank(a[0], wanted) - searchSuggestRank(b[0], wanted) || b[1] - a[1])
      .slice(0, SEARCH_SUGGEST_LIMITS.tag);
    for (const [tag, count] of hits) {
      items.push({ kind: "tag", label: tag, value: `${head}${op}${tag}`, about: `Tag, ${count} note${count === 1 ? "" : "s"}` });
    }
  }
  if (wantsCategories && wanted) {
    const hits = [...words.categories.entries()]
      .filter(([name]) => searchSuggestRank(name, wanted) >= 0 && name.toLowerCase() !== wanted)
      .sort((a, b) => searchSuggestRank(a[0], wanted) - searchSuggestRank(b[0], wanted) || b[1] - a[1])
      .slice(0, SEARCH_SUGGEST_LIMITS.category);
    for (const [name, count] of hits) {
      const written = op && /\s/.test(name) ? `"${name}"` : name;
      items.push({ kind: "category", label: name, value: `${head}${op}${written}`, about: `Category, ${count} note${count === 1 ? "" : "s"}` });
    }
  }
  return items;
}

const SEARCH_SUGGEST_ICONS = { recent: "ph:clock-counter-clockwise", item: "ph:list-magnifying-glass", title: "ph:note", tag: "ph:hash", category: "ph:folder-simple" };
const SEARCH_SUGGEST_GROUPS = { recent: "Recent searches", item: "In this list", title: "Notes", tag: "Tags", category: "Categories" };

function closeSearchSuggest() {
  if (!searchSuggest) return;
  const { input, box, ghost, onInput, onKey, onBlur, onWindow, onScroll } = searchSuggest;
  input.removeEventListener("input", onInput);
  input.removeEventListener("keydown", onKey, true);
  input.removeEventListener("blur", onBlur);
  window.removeEventListener("resize", onWindow);
  window.removeEventListener("scroll", onScroll, true);
  input.setAttribute("aria-expanded", "false");
  input.removeAttribute("aria-activedescendant");
  box.remove();
  ghost.remove();
  searchSuggest = null;
}

//: Below the box when it fits, above when the window's foot is near; the
//: box's own width, never wider than the window.
function placeSearchSuggest() {
  const { input, box } = searchSuggest;
  const field = (input.closest(".search-field, .finder-bar, .web-search-field") || input).getBoundingClientRect();
  const room = { below: window.innerHeight - field.bottom, above: field.top };
  //: As wide as the box it belongs to, never narrower than the list's own
  //: default (288px), left on the box, inside the window with a 16px gutter
  //: (INBOX 849).
  const width = Math.min(Math.max(field.width, 288), window.innerWidth - 32);
  box.style.left = `${Math.max(16, Math.min(field.left, window.innerWidth - width - 16))}px`;
  box.style.width = `${width}px`;
  if (room.below >= 200 || room.below >= room.above) {
    box.style.top = `${field.bottom + 4}px`;
    box.style.bottom = "auto";
    box.style.maxHeight = `${Math.max(120, Math.min(340, room.below - 12))}px`;
  } else {
    box.style.top = "auto";
    box.style.bottom = `${window.innerHeight - field.top + 4}px`;
    box.style.maxHeight = `${Math.max(120, Math.min(340, room.above - 12))}px`;
  }
  placeSearchGhost();
}


//: The grey remainder of the best completion, laid over the box's own text
//: line: where the typed text ends, measured with the box's own font.
function placeSearchGhost() {
  const { input, ghost, ghostItem } = searchSuggest;
  const typed = input.value;
  const atEnd = input.selectionStart === typed.length && input.selectionEnd === typed.length;
  if (!ghostItem || !atEnd || document.activeElement !== input) {
    ghost.classList.add("hidden");
    return;
  }
  const rest = ghostItem.value.slice(typed.length);
  const style = getComputedStyle(input);
  searchSuggestCache.measure = searchSuggestCache.measure || document.createElement("canvas").getContext("2d");
  searchSuggestCache.measure.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  const rect = input.getBoundingClientRect();
  const left = rect.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft) + searchSuggestCache.measure.measureText(typed).width - input.scrollLeft;
  const right = rect.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight);
  if (left >= right - 4) {
    ghost.classList.add("hidden");
    return;
  }
  ghost.textContent = rest;
  ghost.style.font = style.font;
  ghost.style.letterSpacing = style.letterSpacing;
  ghost.style.left = `${left}px`;
  ghost.style.top = `${rect.top + parseFloat(style.borderTopWidth) + parseFloat(style.paddingTop)}px`;
  ghost.style.height = `${rect.height - parseFloat(style.borderTopWidth) - parseFloat(style.borderBottomWidth) - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)}px`;
  ghost.style.maxWidth = `${right - left}px`;
  ghost.classList.remove("hidden");
}

function fillSearchSuggest() {
  const state = searchSuggest;
  const { input, list, foot } = state;
  const items = state.quiet ? [] : searchSuggestItems(input);
  const rows = [];
  const nodes = [];
  let group = "";
  items.forEach((item, i) => {
    if (item.kind !== group) {
      group = item.kind;
      nodes.push(richPickerGroup(SEARCH_SUGGEST_GROUPS[group]));
    }
    const row = richPickerRow({
      icon: SEARCH_SUGGEST_ICONS[item.kind],
      label: item.label,
      about: item.about,
      query: input.value.trim(),
      id: `search-suggest-${i}`,
    });
    row.dataset.kind = item.kind;
    if (item.kind === "recent") {
      //: Pointer only (aria-hidden, not a button inside an option): the keys
      //: are Shift+Delete and the foot's Clear, named in the foot.
      row.classList.add("search-suggest-recent");
      const remove = document.createElement("span");
      remove.className = "search-suggest-remove";
      remove.setAttribute("aria-hidden", "true");
      remove.title = "Remove this recent search";
      const glyph = document.createElement("i");
      glyph.className = "ph ph-x";
      remove.appendChild(glyph);
      row.appendChild(remove);
    }
    row.addEventListener("pointermove", () => {
      if (!searchSuggest || searchSuggest.active === i) return;
      searchSuggest.active = i;
      searchSuggest.moved = true;
      richPickerSetActive(list, rows, i);
      input.setAttribute("aria-activedescendant", row.id);
    });
    row.addEventListener("pointerdown", (event) => {
      event.preventDefault(); // keep the focus in the box
      if (event.target.closest(".search-suggest-remove")) removeSearchSuggest(item);
      else takeSearchSuggest(item, { commit: true });
    });
    rows.push(row);
    nodes.push(row);
  });
  list.replaceChildren(...nodes);
  state.items = items;
  state.rows = rows;
  state.moved = false;
  state.active = -1;
  richPickerSetActive(list, rows, -1);
  input.removeAttribute("aria-activedescendant");
  //: The best completion: the first suggestion whose text continues what is typed.
  const typed = input.value.toLowerCase();
  state.ghostItem = typed ? items.find((item) => item.value.length > typed.length && item.value.toLowerCase().startsWith(typed)) || null : null;
  const hasRecent = items.some((item) => item.kind === "recent");
  foot.classList.toggle("hidden", !hasRecent);
  state.box.classList.toggle("hidden", !items.length);
  input.setAttribute("aria-expanded", String(items.length > 0));
  if (items.length && state.announced !== items.length) {
    state.announced = items.length;
    announce(`${items.length} suggestion${items.length === 1 ? "" : "s"}`);
  }
  if (!items.length) state.announced = 0;
  placeSearchSuggest();
}

//: **The box can move after the list opens**: a dock re-flowing as a tab
//: arrives, or as the list of notes it filters changes length (measured: the
//: ghost text stood 60px right of the caret after a filter shortened the label
//: beside the field). The list and the ghost are placed again shortly after
//: it opens and after each keystroke, which is when that happens, and on a
//: resize or scroll. No frame loop: the app counts every one it runs
//: (tests/test_frontend_wake_sources.py), and an open list is idle.
function placeSearchSuggestSoon() {
  const state = searchSuggest;
  for (const ms of [120, 400]) setTimeout(() => searchSuggest === state && placeSearchSuggest(), ms);
}

//: Put a suggestion in the box. `commit` is a press: the box's own search
//: runs by the `input` event, and the words are remembered as recent.
function takeSearchSuggest(item, { commit = false } = {}) {
  const state = searchSuggest;
  if (!state) return;
  const { input } = state;
  state.accepting = true;
  input.value = item.value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.setSelectionRange(input.value.length, input.value.length);
  state.accepting = false;
  if (commit) searchSuggestRemember(input);
  //: Shut until the next key: what was taken is not suggested back at once.
  state.quiet = true;
  fillSearchSuggest();
}

function removeSearchSuggest(item) {
  const state = searchSuggest;
  if (!state) return;
  const scope = searchSuggestScopeOf(state.input);
  searchRecent.remove(scope, item.value);
  fillSearchSuggest();
  if (scope === "web") renderWebSearchHistory();
  announce("Removed from recent searches.");
}

//: One box's recents forgotten, from the box's own Clear or the web panel's,
//: with the way back for ten seconds and a row in Settings, Recent changes (the
//: same shape as the Settings clears: settings-data.js `settingsClearDone`).
async function clearRecentSearches(scope) {
  const before = searchRecent.load(scope);
  if (!before.length) return;
  searchRecent.clear(scope);
  if (scope === "web") {
    renderWebSearchHistory();
    renderWebPanelMenu(webEngineInfo);
  }
  await ensureModule("settingsData");
  settingsClearDone(
    { kind: "recents", changes: [], words: scope === "web" ? "Cleared recent web searches" : "Cleared recent searches", data: { before: { [scope]: before } } },
    scope === "web" ? "Recent web searches cleared." : "Recent searches cleared."
  );
}

async function clearSearchSuggestRecents() {
  const state = searchSuggest;
  if (!state) return;
  await clearRecentSearches(searchSuggestScopeOf(state.input));
  if (searchSuggest === state) fillSearchSuggest();
}

//: A search that was run is a search worth coming back to. The web panel
//: records its own once the engine has answered, so it is left out here.
function searchSuggestRemember(input, minimum = 2) {
  const scope = searchSuggestScopeOf(input);
  if (!scope || scope === "web") return;
  if (input.value.trim().length >= minimum) searchRecent.push(scope, input.value);
}

//: The entry point (app.js `LAZY_ENTRY_POINTS.searchSuggest`): opens the list
//: under `input`, or refreshes it when it is already open there.
function openSearchSuggest(input) {
  if (!searchSuggestScopeOf(input) || !searchSuggestEnabled()) return;
  if (searchSuggest && searchSuggest.input === input) {
    if (!searchSuggest.accepting) {
      searchSuggest.quiet = false;
      fillSearchSuggest();
    }
    return;
  }
  closeSearchSuggest();
  if (document.activeElement !== input) return;
  const box = document.createElement("div");
  box.className = "search-suggest card hidden";
  const list = document.createElement("ul");
  list.className = "rich-picker-list search-suggest-list";
  list.setAttribute("role", "listbox");
  list.id = "search-suggest-list";
  list.setAttribute("aria-label", "Search suggestions");
  const foot = document.createElement("div");
  foot.className = "search-suggest-foot hidden";
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "link-button search-suggest-clear";
  clear.textContent = "Clear recent searches";
  clear.title = "Forget the recent searches in this box";
  clear.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    clearSearchSuggestRecents();
  });
  clear.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") clearSearchSuggestRecents();
  });
  const hint = document.createElement("span");
  hint.className = "search-suggest-hint";
  hint.textContent = "Shift+Delete removes";
  foot.append(clear, hint);
  box.append(list, foot);
  const ghost = document.createElement("span");
  ghost.className = "search-suggest-ghost hidden";
  ghost.setAttribute("aria-hidden", "true");
  document.body.append(box, ghost);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "both");
  input.setAttribute("aria-haspopup", "listbox");
  input.setAttribute("aria-controls", list.id);
  const onInput = () => {
    if (!searchSuggest || searchSuggest.accepting) return;
    searchSuggest.quiet = false;
    searchSuggest.touched = performance.now();
    fillSearchSuggest();
    placeSearchSuggestSoon();
  };
  const onKey = (event) => {
    const state = searchSuggest;
    if (!state) return;
    const open = !state.box.classList.contains("hidden") && state.rows.length > 0;
    const atEnd = input.selectionStart === input.value.length && input.selectionEnd === input.value.length;
    const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
    if (step && open) {
      event.preventDefault();
      event.stopImmediatePropagation(); // the box's own Up and Down walk its results
      state.active = state.active === -1 ? (step === 1 ? 0 : state.rows.length - 1) : (state.active + step + state.rows.length) % state.rows.length;
      state.moved = true;
      const lit = richPickerSetActive(state.list, state.rows, state.active);
      input.setAttribute("aria-activedescendant", lit?.id || "");
      lit?.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter") {
      //: A lit row is taken and the box's own Enter goes on to search it; an
      //: untouched list leaves Enter alone.
      if (open && state.moved && state.active >= 0) takeSearchSuggest(state.items[state.active], { commit: true });
      else searchSuggestRemember(input);
    } else if (event.key === "Tab" && !event.shiftKey && open && (state.moved || state.ghostItem)) {
      event.preventDefault();
      takeSearchSuggest(state.moved && state.active >= 0 ? state.items[state.active] : state.ghostItem);
    } else if (event.key === "ArrowRight" && open && atEnd && state.ghostItem && !event.shiftKey) {
      event.preventDefault();
      takeSearchSuggest(state.ghostItem);
    } else if (event.key === "Delete" && event.shiftKey && open && state.moved && state.items[state.active]?.kind === "recent") {
      event.preventDefault();
      removeSearchSuggest(state.items[state.active]);
    }
  };
  const onBlur = () => closeSearchSuggest();
  const onWindow = () => searchSuggest && placeSearchSuggest();
  //: **The page or results behind the list scrolling closes it** (INBOX 1330,
  //: "easier to close"): the list stays where it was drawn, so it would hang
  //: over the wrong rows. Its own scrolling does not, nor does the scroll a
  //: browser makes to bring the box into view just after opening or a
  //: keystroke (400ms). Closing is the Escape state: shut until the next key.
  const onScroll = (event) => {
    const state = searchSuggest;
    if (!state || event.target === input || (event.target instanceof Node && state.box.contains(event.target))) return;
    if (performance.now() - state.touched < 400 || state.box.classList.contains("hidden")) return;
    state.quiet = true;
    fillSearchSuggest();
  };
  input.addEventListener("input", onInput);
  input.addEventListener("keydown", onKey, true);
  input.addEventListener("blur", onBlur);
  window.addEventListener("resize", onWindow);
  window.addEventListener("scroll", onScroll, true);
  searchSuggest = { input, box, list, foot, ghost, items: [], rows: [], active: -1, moved: false, quiet: false, accepting: false, ghostItem: null, announced: 0, touched: performance.now(), onInput, onKey, onBlur, onWindow, onScroll };
  fillSearchSuggest();
  placeSearchSuggestSoon();
}

//: Escape closes the list before it closes anything behind it (Find anything
//: closes on a captured Escape of its own): this runs first, on the window.
window.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !searchSuggest || searchSuggest.box.classList.contains("hidden")) return;
  event.stopPropagation();
  event.preventDefault();
  searchSuggest.quiet = true;
  fillSearchSuggest();
}, true);

//: A search is remembered when its box is left with something typed in it
//: (three letters at least: a half-typed word is not a search), as well as on
//: Enter and on a press of a suggestion.
document.addEventListener("change", (event) => {
  if (event.target.matches?.("input[data-search-scope]")) searchSuggestRemember(event.target, 3);
});
