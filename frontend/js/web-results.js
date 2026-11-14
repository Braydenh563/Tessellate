// web-results.js: the web panel's search, its result rows and its recent
// searches. Lazy, with web-clip.js (app.js `LAZY_MODULES.webClip`, which also
// holds the stand-ins for `runWebSearch` and `renderWebSearchHistory`; the
// reader's buttons only exist once `openWebReader` has loaded it): the panel
// is opened by a gesture and none of this is drawn before it (the gzip
// budget). `loadWebSearchHistory` and `clearWebSearchHistory` stay in chat.js.
// One closure; what other files call is the `Object.assign` at the foot.
(() => {
  //: What the dot says, word for word, in its title and its accessible name.
  //: "Stopped" means two different things by provider: under Automatic a search
  //: falls back to DuckDuckGo, and under SearXNG only it does not (websearch.py,
  //: `search_web`), so the sentence names which.
  function webEngineWords(state, provider) {
    const words = {
      off: "Web access is off",
      remote: "Searching with DuckDuckGo: your queries leave this machine",
      running: "SearXNG is running: your searches stay on this machine",
      starting: "SearXNG is starting",
      installing: "SearXNG is installing",
      stopped:
        provider === "searxng"
          ? "SearXNG is stopped, so searches will fail until you start it"
          : "SearXNG is stopped, so searches go to DuckDuckGo",
      absent: "SearXNG is not installed, so searches go to DuckDuckGo",
      unknown: "Search engine: checking",
    };
    return words[state] || words.unknown;
  }

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

  //: Saves a web result straight into the app's own bookmarks. Reports the
  //: duplicate case rather than silently making a second row: the endpoint
  //: already tells us (`duplicate_of`), and "saved" for something that was
  //: already saved is a small lie that makes the list look wrong later.
  async function bookmarkWebResult(result) {
    try {
      const saved = await apiJson("/bookmarks", {
        method: "POST",
        body: JSON.stringify({
          fetch: true,
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

  //: **The one way the app starts SearXNG** (INBOX 1556; Settings, the Ask
  //: offer, the web panel's menu and its failure row all come here, after
  //: `ensureModule("webClip")`). `say` gets the wait line (the first run
  //: downloads it); the preferences are re-read because starting also points
  //: web search at the instance.
  async function startSearxng(first, say) {
    say(first ? "Setting SearXNG up… the first run downloads it, so give it a minute." : "Starting SearXNG…");
    const body = await apiJson("/websearch/searxng/start", { method: "POST" });
    prefsCache = await apiJson("/preferences").catch(() => prefsCache);
    return body;
  }

  //: The panel menu's Start, Install and Stop.
  async function setWebSearxngRunning(start) {
    try {
      if (start) await startSearxng(webEngineInfo?.state === "absent", toast);
      else {
        await apiJson("/websearch/searxng/stop", { method: "POST" });
        toast("Stopping SearXNG.");
      }
    } catch (error) {
      toast(error.message, true);
    }
    refreshWebSearxngStrip();
  }

  //: **The way out of "SearXNG is down"** (INBOX 1556), drawn by the web panel's
  //: failure line and by a failed web-search tool chip, so the two cannot
  //: drift. A button starts it (or installs it when it is absent) through
  //: `startSearxng`; where this device or this machine cannot, one line says why
  //: and Web search settings is beside it. `onRunning` is the search to run
  //: again once it answers; without one the line says to ask again.
  async function searxngDownRow({ onRunning } = {}) {
    const row = document.createElement("span");
    row.className = "searxng-down";
    const line = document.createElement("span");
    line.className = "searxng-down-line";
    const settings = smallButton("ph:gear Web search settings", "Open Web search settings", () => openSettingsModal("websearch"));
    const info = await apiJson("/websearch/searxng/status", { silent: true }).catch(() => null);
    const why = onOtherDevice()
      ? THIS_COMPUTER_ONLY
      : info && !info.backend
        ? info.detail || "SearXNG can't be set up automatically on this computer."
        : "";
    if (why) {
      line.textContent = why;
      row.append(line, settings);
      return row;
    }
    const absent = info?.state === "absent";
    //: **The search runs itself once the engine answers** (L167 and L-chat-20, "a button to auto retry when searxng or
    //: another engine is available"): started here, from Settings or from a terminal, the same search goes again once,
    //: and the line says so. A press that already retried (`retried`) is not retried twice.
    let retried = false;
    const retry = () => {
      if (retried) return;
      retried = true;
      if (onRunning) onRunning();
      else {
        line.textContent = "SearXNG is running. Ask again and web search will use it.";
        row.querySelector(".searxng-start")?.remove();
      }
    };
    const start = smallButton(
      absent ? "ph:download-simple Install SearXNG" : "ph:play Start SearXNG",
      absent ? "Install SearXNG here and start it" : "Start the local SearXNG instance",
      async () => {
        start.disabled = true;
        const say = (text) => { line.textContent = text; };
        try {
          await startSearxng(absent, say);
        } catch (error) {
          //: An install runs on after the press says so; wait for it, then go on.
          const now = await apiJson("/websearch/searxng/status", { silent: true }).catch(() => null);
          if (!now?.installing) {
            say(error.message);
            start.disabled = false;
            row.append(settings);
            return;
          }
          say("Setting SearXNG up… the first run downloads it, so give it a minute.");
          if (!(await waitForSearxng())) {
            say("SearXNG is still setting up. Try the search again in a few minutes.");
            start.disabled = false;
            return;
          }
        }
        retry();
      }
    );
    start.classList.add("searxng-start");
    row.append(line, start);
    watchSearxngReady(row, retry);
    return row;
  }

  //: Asks the status route every four seconds while `row` is on the page (a row drawn and gone, a new question, ends it)
  //: and calls `ready` once, when the engine runs and answers; gives up after ten minutes.
  function watchSearxngReady(row, ready) {
    const step = async (waited) => {
      if (waited > 600000 || !row.isConnected) return;
      const now = await apiJson("/websearch/searxng/status", { silent: true }).catch(() => null);
      if (now?.state === "running" && now.responding && row.isConnected) return ready();
      setTimeout(() => step(waited + 4000), 4000);
    };
    setTimeout(() => step(4000), 4000);
  }

  //: True once the managed SearXNG answers, false after ten minutes or when the
  //: install gives up; the status route is the same one the menu polls.
  async function waitForSearxng() {
    for (let waited = 0; waited < 600000; waited += 3000) {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      const now = await apiJson("/websearch/searxng/status", { silent: true }).catch(() => null);
      if (now?.state === "running" && now.responding) return true;
      if (now && !now.installing && now.state !== "running" && now.state !== "starting") return false;
    }
    return false;
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
      const again = smallButton("ph:arrow-clockwise Try again", "Search again", () => runWebSearch());
      status.replaceChildren(`${error.message} `, again);
      //: SearXNG down is told by the code the server sends, never by the words.
      if (error.body?.code === "searxng_down") {
        searxngDownRow({ onRunning: () => runWebSearch() }).then((row) => {
          if (status.contains(again)) status.append(row);
        });
      }
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

  Object.assign(window, { webEngineWords, bookmarkWebResult, renderWebSearchHistory, startSearxng, setWebSearxngRunning, searxngDownRow, runWebSearch });
})();
