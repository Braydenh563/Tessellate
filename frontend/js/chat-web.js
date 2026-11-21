// chat-web.js: the chat web panel, the reader, the SearXNG strip and citing a page. A classic script sharing the page globals, split out of chat.js (L-world-class-770); loaded right after it.

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

let webReaderPage = null; // the page currently open in the reader
//: The request in flight, a search or a page, so Stop can cancel it and a
//: second search supersedes the first rather than racing it. Without this a
//: slow first answer could land after a fast second one and replace it.
let webRequest = null;

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

function webReaderIsOpen() {
  return !$("web-reader").classList.contains("hidden");
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
let webSearxngTimer = null;

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
let webPanelMenuKey = "";

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
  if (hasHistory) {
    items.push({
      label: "ph:clock-counter-clockwise Clear recent searches",
      title: "Forget the searches listed under the field",
      run: clearWebSearchHistory,
    });
  }
  host.replaceChildren(kebabMenu(items, "Web search options"));
}

//: **The engine's last known state, so the menu is not empty while Docker
//: answers** (the owner, 2026-10-10: "the start searxng button doesnt appear
//: for a while"; driven with the status call held 4000 ms: the control came
//: at 4017 ms). A fresh page has no answer yet and the call can take seconds,
//: so the settled one is kept under `webEngine` and drawn first; the call
//: still has the last word.
let webEngineInfo = prefs.json("webEngine");

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

//: The reader itself is in web-clip.js (lazy; the boot gzip ratchet).
function openWebReader(url) {
  $("web-status").textContent = "Opening…";
  ensureModule("webClip").then(() => showWebReader(url));
}

//: The reader's blocks as plain Markdown, shared by Save as note and Cite in
//: chat so the two cannot disagree about what the page says.
function webPageMarkdown(page) {
  return (page.blocks || [])
    .map((b) =>
      b.type === "heading"
        ? `\n${"#".repeat(Math.min(6, (b.level || 2) + 1))} ${b.text}`
        : b.type === "li"
          ? `- ${b.text}`
          : b.text
    )
    .join("\n")
    .trim();
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
let attachedWebPage = null;
//: The page the last answer cited, for a spoken ask about that page (`webFollowUp`).
//: A field rather than a top-level `let` (the global-scope ratchet): it was
//: taken out as "never read" while chat-attach.js still read it, so every
//: Chat send threw a ReferenceError (found by Brief 67's sweep).
const chatWeb = { lastUrl: null };
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
      toast(error.message || voiceLine("failed", "read that page"), true);
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
