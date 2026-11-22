// web-panel.js: the web search and reader panel's code (toggle, Stop, the engine dot and
// menu, recents, Ask about this, Cite in chat). Moved out of chat.js (LEDGER L-world-class-571)
// to come out of the boot gzip budget. Lazy, in the `webClip` bundle before web-clip.js; its
// state (`webReaderPage`, `webRequest`, `webEngineInfo`, `attachedWebPage`, `chatWeb`) and the two
// synchronous readers (`webReaderIsOpen`, `webPageMarkdown`) stay in chat.js, and lazy-entries.js
// holds stand-ins for what boot code calls.
let webSearxngTimer = null;
let webPanelMenuKey = "";

// --- web panel: search + reader view ----------------------------------------
// Deliberately not an embedded browser. Pages are fetched and stripped to
// text by the backend, so nothing from a third-party site ever executes here.
//
//: **A reading pane, not a form** (the owner, 2026-09-24: "the web browser
//: sidebar needs a major improved modern and professional redesign and
//: feature improvement"). Measured before with
//: `scratchpad/ui-sweeps/webpanel.js`: four boxed controls above the results
//: in two heights and two radii, the engine's state as a box with its own
//: boxed Stop, three worded buttons stacked over the page, and the page text
//: in a bordered box that scrolled inside a column that also scrolled. The
//: shape now is the one every reader pane the owner compares it to shares
//: (Arc's side panel, Safari's reader, Perplexity's sources): a quiet head, one
//: field, a list, and a page.


function webRequestStart() {
  webRequest?.abort();
  const controller = new AbortController();
  webRequest = controller;
  $("web-stop").classList.remove("hidden");
  $("web-panel").setAttribute("aria-busy", "true");
  return controller;
}

function webRequestEnd(controller) {
  //: Only the request that is still current may clear the busy state: an
  //: aborted one finishing late must not hide the Stop of its successor.
  if (webRequest !== controller) return false;
  webRequest = null;
  $("web-stop").classList.add("hidden");
  $("web-panel").removeAttribute("aria-busy");
  return true;
}

function stopWebRequest() {
  const controller = webRequest;
  if (!controller) return;
  controller.abort();
  webRequestEnd(controller);
  const status = $("web-status");
  status.classList.remove("error");
  status.textContent = "Stopped.";
  $("web-query").focus();
}


function closeWebReader() {
  $("web-reader").classList.add("hidden");
  renderWebSearchHistory();
  //: Back lands where it left: on the result that was opened, so the arrow
  //: keys carry on down the list from there rather than from the top.
  const opened = webReaderPage
    ? [...document.querySelectorAll("#web-results .web-result-title")].find(
        (el) => el.dataset.url === webReaderPage.url
      )
    : null;
  (opened || $("web-query")).focus();
}

function toggleWebPanel(force) {
  const panel = $("web-panel");
  const show = force ?? panel.classList.contains("hidden");
  panel.classList.toggle("hidden", !show);
  //: A class the narrow layout's CSS reads, not a `:has()` on the column (AI9).
  panel.closest(".tab-main")?.classList.toggle("web-open", show);
  if (show) {
    // Say up front when searching cannot work, rather than after a search has
    // failed. Web access is off by default, this is a local-first app and
    // that is the right default, so the commonest first experience of this
    // panel is typing a query into a box that was never going to answer. The
    // switch is one click away, and naming where it lives is the difference
    // between a dead end and a setting.
    const status = $("web-status");
    if (prefsCache && !prefsCache.web_search_enabled) {
      status.replaceChildren();
      status.classList.remove("error");
      status.appendChild(
        document.createTextNode("Web access is off. Turn it on in ")
      );
      const link = document.createElement("button");
      link.type = "button";
      link.className = "link-button";
      link.textContent = "Settings, Web search";
      link.addEventListener("click", () => {
        toggleWebPanel(false);
        openSettingsModal("websearch");
      });
      status.appendChild(link);
      status.appendChild(document.createTextNode(" to search from here."));
    } else if (!$("web-results").childElementCount) {
      status.textContent = "";
    }
    //: The "..." is drawn with the head, from what was last known; the
    //: status call below (seconds while Docker answers) only updates it.
    renderWebPanelMenu(webEngineInfo);
    //: Private web search needs SearXNG: the optional-package notice (extra-notice.js).
    if (prefsCache && prefsCache.web_search_enabled && prefsCache.search_provider !== "duckduckgo") extraNoticeMount(panel, "searxng");
    refreshWebSearxngStrip();
    renderWebSearchHistory();
    //: The page you were reading is still there when the panel comes back.
    //: Closing it used to throw the reader away, so glancing at the
    //: conversation cost you your place in the article.
    if (!webReaderIsOpen()) $("web-query").focus();
  } else {
    clearTimeout(webSearxngTimer);
    if (webRequest) {
      webRequest.abort();
      webRequestEnd(webRequest);
    }
  }
}

// Feedforward for whether the private, local SearXNG instance is actually
// running: not just the after-the-fact "answered by SearXNG" a result
// already carries. Deliberately far lighter than Settings, Web search's
// full management UI (install progress, port diagnostics, reinstall): only
// "is it on", as a dot in the head, and "turn it on or off", in the kebab
// beside it.

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

function setWebEngineDot(state, provider) {
  const dot = $("web-engine-dot");
  const words = webEngineWords(state, provider);
  dot.dataset.state = state;
  dot.title = words;
  dot.setAttribute("aria-label", words);
}

//: The head's kebab: the engine's one command, the settings behind it, and
//: the recent searches. Rebuilt only when what it would say changes, and
//: never while it is open, since replacing an open menu's opener strands the
//: menu `kebabMenu` has already moved to <body>.

function renderWebPanelMenu(engine) {
  const host = $("web-panel-menu");
  if (!host) return;
  const hasHistory = loadWebSearchHistory().length > 0;
  const key = `${engine?.state || ""}|${engine?.running ? 1 : 0}|${hasHistory ? 1 : 0}`;
  if (key === webPanelMenuKey && host.firstChild) return;
  if (host.querySelector("[aria-expanded='true']")) return;
  webPanelMenuKey = key;
  const items = [];
  if (engine) {
    if (engine.state === "installing") {
      items.push({
        label: "ph:hourglass Installing SearXNG",
        title: "SearXNG is installing; Settings, Web search shows its progress",
        disabled: true,
        run: () => openSettingsModal("websearch"),
      });
    } else if (engine.running) {
      items.push({
        label: "ph:stop-circle Stop SearXNG",
        title: "Stop the local SearXNG instance",
        run: () => ensureModule("webClip").then(() => setWebSearxngRunning(false)),
      });
    } else {
      items.push({
        label: engine.state === "absent" ? "ph:download-simple Install SearXNG" : "ph:play Start SearXNG",
        title:
          engine.state === "absent"
            ? "Install SearXNG locally and start it, searches then never leave this machine"
            : "Start the local SearXNG instance",
        run: () => ensureModule("webClip").then(() => setWebSearxngRunning(true)),
      });
    }
  }
  items.push({
    label: "ph:gear-six Web search settings",
    title: "Choose the engine and manage SearXNG in Settings",
    run: () => openSettingsModal("websearch"),
  });
  items.push({
    label: "ph:bookmark-simple Clip a page from your browser",
    title: "Keep a page you are reading elsewhere as a note: Settings, Import & export, Web clipper",
    run: () => openSettingsModal("data", "web-clip-box"),
  });
  if (hasHistory) {
    items.push({
      label: "ph:clock-counter-clockwise Clear recent searches",
      title: "Forget the searches listed under the field",
      run: clearWebSearchHistory,
    });
  }
  host.replaceChildren(kebabMenu(items, "Web search options"));
}


//: **Said at open, not after a search fails** (the owner 2026-11-22: "nothing
//: tells the user that SearXNG isn't running until a search fails"). A `.notice`
//: between the head and the field while SearXNG is installed but stopped (or
//: starting) and the provider would use it; its words are the dot's, so the two
//: never disagree. Absent is the package notice's (`extraNoticeMount`), and
//: DuckDuckGo or web access off never touch SearXNG, so none is drawn there.
function renderWebEngineNotice(state, provider) {
  const panel = $("web-panel");
  let notice = panel.querySelector(".web-engine-notice");
  const show =
    (!prefsCache || prefsCache.web_search_enabled) &&
    provider !== "duckduckgo" &&
    (state === "stopped" || state === "starting");
  if (!show) {
    notice?.remove();
    return;
  }
  if (!notice) {
    notice = document.createElement("p");
    notice.className = "notice web-engine-notice";
    notice.setAttribute("role", "status");
    panel.querySelector(".web-search-field").before(notice);
  }
  const words = document.createElement("span");
  setLabel(words, `ph:${state === "starting" ? "hourglass" : "power"} ${provider === "searxng" && state === "stopped" ? "Web search is off: SearXNG is stopped" : webEngineWords(state, provider)}`);
  const parts = [words];
  if (state === "stopped") {
    const start = smallButton("ph:play Start", "Start the local SearXNG instance", () => {
      start.disabled = true;
      setWebSearxngRunning(true);
    });
    parts.push(start);
  }
  notice.replaceChildren(...parts);
}

async function refreshWebSearxngStrip() {
  await ensureModule("webClip");
  const provider = (prefsCache && prefsCache.search_provider) || "auto";
  clearTimeout(webSearxngTimer);
  if (prefsCache && !prefsCache.web_search_enabled) {
    setWebEngineDot("off", provider);
  } else if (provider === "duckduckgo") {
    setWebEngineDot("remote", provider);
  }
  //: DuckDuckGo never touches SearXNG, so the dot above keeps saying DuckDuckGo
  //: answers; the menu still offers the engine's command, since starting it is
  //: how someone on DuckDuckGo gets to try SearXNG (B55: the item was "gone").
  const info = await apiJson("/websearch/searxng/status").catch(() => null);
  if (!info || !info.backend) {
    // No usable backend (Docker or a virtualenv) to run it at all, Settings
    // → Web search explains why; there is nothing to start from here.
    webEngineInfo = null;
    if (!prefsCache || prefsCache.web_search_enabled) setWebEngineDot("remote", provider);
    renderWebEngineNotice(null, provider);
    renderWebPanelMenu(null);
    return;
  }
  const running = info.state === "running" && info.responding;
  const state = info.installing
    ? "installing"
    : running
      ? "running"
      : { running: "starting", absent: "absent" }[info.state] || "stopped";
  webEngineInfo = { state, running };
  prefs.setJSON("webEngine", webEngineInfo);
  if (!prefsCache || prefsCache.web_search_enabled) setWebEngineDot(provider === "duckduckgo" ? "remote" : state, provider);
  renderWebEngineNotice(state, provider);
  renderWebPanelMenu(webEngineInfo);
  // Keep polling while it settles, same as Settings' own richer view:
  // otherwise "starting" can stick with no way to tell it's still moving.
  if (state === "installing" || state === "starting") {
    webSearxngTimer = setTimeout(refreshWebSearxngStrip, state === "installing" ? 2000 : 3000);
  }
}

// Last few distinct web queries, newest first, asked for directly ("missing
// features... history"). Client-side only: these are the person's own past
// searches, same privacy tier as the search itself (already opt-in, already
// logged locally via manager.log_action), nothing new leaves the machine.
const WEB_SEARCH_HISTORY_KEY = "webSearchHistory";
function loadWebSearchHistory() {
  try {
    const raw = prefs.json(WEB_SEARCH_HISTORY_KEY, []);
    return Array.isArray(raw) ? raw.filter((q) => typeof q === "string") : [];
  } catch {
    return [];
  }
}

//: Forget the web panel's recents with the way back for ten seconds, and a row
//: in Settings, Recent changes (search-suggest.js `clearRecentSearches`, lazy).
function clearWebSearchHistory() {
  ensureModule("searchSuggest").then(() => clearRecentSearches("web"));
}

// "Ask about this" used to drop `About <url>, ` into the chat box and stop
// there. The model cannot open a URL, so it answered from the address text,
// which is why this read as simply not working (user-reported). It now closes
// the web panel, writes a question naming the page, and lets the agent's
// read_url tool fetch it. The tool needs web search on, so that is checked
// first and offered rather than failing silently.
async function askAboutPage(url, title) {
  if (!(prefsCache && prefsCache.web_search_enabled)) {
    toast("Turn on Web search first, reading a page needs it.", "info");
    return;
  }
  // Reading a page is a tool call, so agent mode has to be on for this turn.
  const input = $("chat-input");
  const label = (title || "").trim() || url;
  input.value = `Read ${url} and tell me about it, "${label}".`;
  toggleWebPanel(false);
  input.focus();
  // Sent with tools forced on, whatever the toggle says: the request is
  // meaningless without the one tool that can fetch the page.
  await sendChatMessage(undefined, { useTools: true });
}

//: The reader itself is in web-clip.js (lazy; the boot gzip ratchet).
function openWebReader(url) {
  $("web-status").textContent = "Opening…";
  ensureModule("webClip").then(() => showWebReader(url));
}

// --- citing a web page in the chat ---------------------------------------------
//: **Cite in chat** attaches a page to the next message as a chip, the way a
//: selection or a note does, so the question is yours rather than the canned
//: one "Ask about this" sends. What the model is given is the text the reader
//: already fetched, so it needs no tool call and no second fetch, and it works
//: in Ask mode as well as Agent.
//:
//: One page at a time, like a selection: a citation is "this, about which I
//: am about to ask", not a collection.
//: The budget for the page's text in the prompt. A long article runs to
//: tens of thousands of characters; the opening of a page is where its claim
//: is, and a local model's context is the scarcest thing in the round.
const WEB_CITE_CHARS = 6000;

async function citeWebPage(pageOrResult) {
  let page = pageOrResult;
  //: A result row has a snippet, not the page: fetch it first, through the
  //: same route the reader uses, so what is cited is what the reader shows.
  if (!page.blocks && !page.text) {
    try {
      page = await apiJson(`/websearch/read?url=${encodeURIComponent(page.url)}`);
    } catch (error) {
      toast(error.message || voiceLine("failed", { what: "read that page" }), true);
      return;
    }
  }
  attachedWebPage = {
    url: page.url,
    title: page.title || page.domain || page.url,
    domain: page.domain || "",
    text: (webPageMarkdown(page) || page.text || "").slice(0, WEB_CITE_CHARS),
  };
  renderWebPageAttachment();
  //: The composer is beside the panel above 1100px; below it the panel covers
  //: the conversation, so it closes to show the chip it just made.
  if (webPanelIsNarrow()) toggleWebPanel(false);
  const input = $("chat-input");
  input?.focus();
  announce(`${attachedWebPage.title} attached to your next message.`);
}

function renderWebPageAttachment() {
  const box = $("chat-web-attachment");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", !attachedWebPage);
  if (!attachedWebPage) return;
  box.appendChild(
    attachmentChip({
      name: attachedWebPage.title,
      icon: "ph-globe",
      facts: attachedWebPage.domain || "Page",
      title: `${attachedWebPage.title} (${attachedWebPage.url})`,
      removeTitle: "Don't send this page with your message",
      onRemove: () => {
        attachedWebPage = null;
        renderWebPageAttachment();
        announce("Page removed.");
      },
    }),
  );
}

