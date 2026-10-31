// web-results.js: the web panel's search, its result rows and its recent
// searches. Lazy, with web-clip.js (app.js `LAZY_MODULES.webClip`, which also
// holds the stand-ins for `runWebSearch` and `renderWebSearchHistory`; the
// reader's buttons only exist once `openWebReader` has loaded it): the panel
// is opened by a gesture and none of this is drawn before it (the gzip
// budget). `loadWebSearchHistory` and `clearWebSearchHistory` stay in chat.js.

const WEB_SEARCH_HISTORY_MAX = 8;
// Results already fetched for the current query but not yet shown, "Show
// more" reveals from here rather than re-searching, since the backend
// already returns up to 20 in one call (routes_websearch.py).
let webSearchPending = [];

//: The favicon's stand-in: the site's first letter on a quiet tile. A real
//: favicon would be a request to the site from inside the app for every
//: result on screen, which is exactly what fetching pages on the server and
//: stripping them to text exists to avoid. The letter still does the job a
//: favicon does in a list, which is to let the eye find "the one from
//: sqlite.org" without reading every domain.
function webResultMark(domain) {
  const mark = document.createElement("span");
  mark.className = "web-result-mark";
  mark.setAttribute("aria-hidden", "true");
  const name = (domain || "").replace(/^www\./, "");
  mark.textContent = (name.match(/[a-z0-9]/i)?.[0] || "?").toUpperCase();
  return mark;
}

//: **The words the search was for, marked inside each snippet** (BACKLOG
//: section 13, "result cards worth reading": a snippet with the matched terms
//: highlighted lets someone judge relevance before opening the reader). The
//: terms are the query's own words, lower-cased, without the little words that
//: would mark half of every sentence ("the", "and", "what") and without
//: one- and two-letter fragments. `highlightInto` (notes-list.js) draws the
//: marks as DOM nodes, the same helper a note card's search uses, so a snippet
//: from the web is never parsed as markup.
const WEB_TERM_STOP_WORDS = new Set(
  ("the and for with that this what when where which who how are was were from " +
    "into your you have has not but can will about").split(" ")
);
function webQueryTerms(query) {
  const terms = [];
  for (const word of String(query || "").toLowerCase().split(/[^\p{L}\p{N}]+/u)) {
    if (word.length > 2 && !WEB_TERM_STOP_WORDS.has(word) && !terms.includes(word)) terms.push(word);
  }
  return terms;
}
//: Set by `runWebSearch` before any row is built, so "Show more" rows revealed
//: later mark the same words as the first eight.
const webResultTerms = [];

// One search result row, split out so the initial batch and the "Show
// more" reveal (below) build identical rows from one code path.
function buildWebResultRow(result) {
  const row = document.createElement("div");
  //: The list-row recipe (DESIGN.md, `.timeline-row`'s shape): mark,
  //: content, actions; the ground arrives with the pointer, never an edge
  //: drawn round every row.
  row.className = "web-result";
  row.appendChild(webResultMark(result.domain));

  //: **Source first, then the headline.** Reported bluntly: "the web search
  //: features and ui and ux are horrible." Half of that was reading order.
  //: Every search surface the user compares this to, Google, Perplexity,
  //: Odysseus's own: puts where a result came from *above* its title,
  //: because deciding whether to trust a result starts with the domain.
  const meta = document.createElement("div");
  meta.className = "web-result-meta";
  const host = document.createElement("span");
  host.className = "web-result-host";
  host.textContent = (result.domain || "").replace(/^www\./, "");
  meta.appendChild(host);
  // SearXNG is a metasearch engine, so "via SearXNG" says where the query
  // was assembled rather than who answered it. Naming the upstream engines
  // is what makes a self-hosted instance legible rather than a black box.
  // textContent throughout: these names come from a third party.
  if (Array.isArray(result.via) && result.via.length) {
    const via = document.createElement("span");
    via.className = "web-result-via";
    via.textContent = result.via.join(" · ");
    via.title = `Found by ${result.via.join(", ")}`;
    meta.append(document.createTextNode(" · "), via);
  }
  row.appendChild(meta);

  //: The title is the row's one tab stop and what the arrow keys walk
  //: (ARROW_NAV_LISTS); Enter on it opens the reader, as a click does.
  const title = document.createElement("button");
  title.type = "button";
  title.className = "web-result-title";
  title.dataset.url = result.url;
  title.textContent = result.title || result.url;
  title.title = `Read “${result.title || result.url}” here, without opening a browser`;
  title.addEventListener("click", () => openWebReader(result.url));
  row.appendChild(title);

  if (result.snippet) {
    const snippet = document.createElement("div");
    snippet.className = "web-result-snippet";
    highlightInto(snippet, result.snippet, webResultTerms);
    row.appendChild(snippet);
  }

  //: **One kebab, not a stacked column of icons.** Always visible (so it is
  //: reachable by touch and by keyboard without a hover), and what every
  //: other list in this app uses. It is also what a right-click on the row
  //: opens (ROW_MENU_HOSTS), so the two cannot disagree. Six rows, so they
  //: are grouped: where you read it, what you do with it, and keeping it.
  const actions = document.createElement("div");
  actions.className = "web-result-actions";
  const label = result.title || result.domain || result.url;
  actions.appendChild(
    kebabMenu(
      [
        {
          group: "read",
          label: "ph:book-open-text Read here",
          title: "Read this page as text, inside Tessellate",
          run: () => openWebReader(result.url),
        },
        {
          group: "read",
          label: "ph:arrow-square-out Open in browser",
          title: "Open this page in your own browser",
          run: () => openWebPageExternally(result.url),
        },
        {
          group: "read",
          label: "ph:link Copy link",
          title: "Copy this page's address",
          run: () => copyWebLink(result.url),
        },
        {
          group: "ask",
          label: "ph:chat-circle Ask Atlas about this",
          title: "Let Atlas fetch this page and answer about it",
          run: () => askAboutPage(result.url, result.title),
        },
        {
          group: "ask",
          label: "ph:quotes Cite in chat",
          title: "Attach this page to your next message",
          run: () => citeWebPage(result),
        },
        {
          //: The one integration this panel never had, and the obvious one:
          //: the app already keeps bookmarks, and "I found something worth
          //: keeping" is what a search result *is*.
          group: "keep",
          label: "ph:bookmark-simple Save as bookmark",
          title: "Keep this link in your bookmarks",
          run: () => bookmarkWebResult(result),
        },
      ],
      `Actions for “${label}”`
    )
  );
  row.appendChild(actions);
  return row;
}

//: `window.open` with `noopener`: in the desktop window pywebview hands a
//: new-window request to the system browser, and in a browser tab it is a
//: new tab. `safeHref` because the URL came from a third party.
function openWebPageExternally(url) {
  window.open(safeHref(url), "_blank", "noopener,noreferrer");
}

async function copyWebLink(url, button) {
  if (await copyToClipboard(url, button)) announce("Link copied.");
}

//: Saves a web result straight into the app's own bookmarks. Reports the
//: duplicate case rather than silently making a second row: the endpoint
//: already tells us (`duplicate_of`), and "saved" for something that was
//: already saved is a small lie that makes the list look wrong later.
async function bookmarkWebResult(result) {
  try {
    const saved = await apiJson("/bookmarks", {
      method: "POST",
      body: JSON.stringify({
        url: result.url,
        title: (result.title || "").slice(0, 200),
        note: (result.snippet || "").slice(0, 2000),
      }),
    });
    if (saved && !saved.duplicate_of && saved.id != null) {
      let liveId = saved.id;
      pushUndo(
        `Bookmarked “${clipText(saved.title || saved.url, 40)}”`,
        () => apiJson(`/bookmarks/${liveId}`, { method: "DELETE" }),
        async () => {
          const again = await apiJson("/bookmarks", { method: "POST", body: JSON.stringify({ url: saved.url, title: saved.title || "", note: saved.note || "" }) });
          liveId = again.id ?? liveId;
        }
      );
    }
    toast(
      saved && saved.duplicate_of
        ? "Already in your bookmarks."
        : `Bookmarked “${saved.title || saved.url}”.`
    );
    return true;
  } catch (error) {
    toast(error.message || "Couldn't save that bookmark.", true);
  }
}

function pushWebSearchHistory(query) {
  const trimmed = query.trim();
  if (!trimmed) return;
  const history = [trimmed, ...loadWebSearchHistory().filter((q) => q !== trimmed)].slice(
    0,
    WEB_SEARCH_HISTORY_MAX
  );
  try {
    prefs.set(WEB_SEARCH_HISTORY_KEY, JSON.stringify(history));
  } catch {
    /* storage full or blocked, the search itself still worked */
  }
}

// Shown only while the query box is empty and nothing is on screen: recent
// searches are a way *in*, not chrome that sits above every result list.
//: Rows rather than the chips they were: a chip is a fact and these are
//: actions (DESIGN.md), and a row has room for a long query where a chip in a
//: 280px column wrapped into a ragged cloud.
function renderWebSearchHistory() {
  const box = $("web-search-history");
  if (!box) return;
  const history = loadWebSearchHistory();
  box.replaceChildren();
  const busy = $("web-query").value.trim() || $("web-results").childElementCount || webReaderIsOpen();
  if (busy || !history.length) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  //: The head carries its own Clear (a visible control, not only the panel's menu).
  const head = document.createElement("div");
  head.className = "web-section-label web-recent-head";
  head.append("Recent", smallButton("Clear recent", "Forget these searches", clearWebSearchHistory));
  box.appendChild(head);
  for (const query of history) {
    const line = document.createElement("div");
    line.className = "web-recent-row";
    const row = smallButton(`ph:clock-counter-clockwise ${query}`, `Search again: ${query}`, () => {
      $("web-query").value = query;
      runWebSearch();
    });
    row.classList.add("web-recent");
    const remove = smallButton("ph:x", `Remove "${query}" from recent searches`, () => {
      prefs.setJSON(WEB_SEARCH_HISTORY_KEY, history.filter((q) => q !== query));
      renderWebSearchHistory();
      renderWebPanelMenu(webEngineInfo);
    });
    remove.classList.add("web-recent-remove");
    line.append(row, remove);
    box.appendChild(line);
  }
}

async function runWebSearch() {
  const query = $("web-query").value.trim();
  if (!query) return;
  const status = $("web-status");
  const box = $("web-results");
  $("web-reader").classList.add("hidden");
  $("web-search-history").classList.add("hidden");
  box.replaceChildren();
  webSearchPending = [];
  status.classList.remove("error");
  setLabel(status, "ph:spin Searching the web…");
  const controller = webRequestStart();
  let body;
  try {
    // Asks for the route's full cap in one call, both providers already
    // fetch one page and slice it, so this costs nothing extra over asking
    // for 8, and "Show more" below can reveal the rest without a second
    // request (or a second hit against a rate limit).
    body = await apiJson(`/websearch?q=${encodeURIComponent(query)}&limit=20`, {
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") return; // Stop, or a newer search
    if (!webRequestEnd(controller)) return;
    status.classList.add("error");
    //: With the way out beside it (the owner, 2026-10-10: "there should be a
    //: retry button for failed web searches").
    status.replaceChildren(`${error.message} `, smallButton("ph:arrow-clockwise Try again", "Search again", () => runWebSearch()));
    return;
  }
  if (!webRequestEnd(controller)) return;
  pushWebSearchHistory(query);
  renderWebPanelMenu(webEngineInfo);
  webResultTerms.splice(0, webResultTerms.length, ...webQueryTerms(query));
  const results = body.results || [];
  // Name the engine that ANSWERED, which under "Automatic" is not
  // necessarily the one configured, and say what that means for privacy.
  // Said on an empty result too: "nothing found" and "nothing found *by
  // DuckDuckGo*" are different facts, and the second is the one you can act on.
  const answered = body.answered_by || { label: body.provider || "", detail: "" };
  status.replaceChildren();
  const summary = document.createElement("span");
  summary.textContent = results.length
    ? `${nounCount(results.length, "result")} via ${answered.label}`
    : `No results from ${answered.label}: try different words.`;
  status.appendChild(summary);
  if (answered.detail) {
    //: Its own line, not " · " glued onto the count. In a narrow panel the
    //: joined version wrapped mid-phrase.
    const detail = document.createElement("span");
    detail.className = "web-answered-detail";
    detail.textContent = answered.detail;
    status.appendChild(detail);
  }

  const INITIAL_SHOWN = 8;
  for (const result of results.slice(0, INITIAL_SHOWN)) {
    box.appendChild(buildWebResultRow(result));
  }
  webSearchPending = results.slice(INITIAL_SHOWN);
  if (webSearchPending.length) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "ghost small web-show-more";
    setLabel(more, `ph:caret-down Show ${webSearchPending.length} more`);
    more.addEventListener("click", () => {
      const first = buildWebResultRow(webSearchPending[0]);
      box.insertBefore(first, more);
      for (const result of webSearchPending.slice(1)) box.insertBefore(buildWebResultRow(result), more);
      webSearchPending = [];
      more.remove();
      //: The focus was on the button that just went away; it goes to the
      //: first row it revealed rather than falling to <body>.
      first.querySelector(".web-result-title")?.focus();
    });
    box.appendChild(more);
  }
}
