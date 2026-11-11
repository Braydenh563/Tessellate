// extra-notice.js: "this feature needs an optional package" (INBOX 1748, Q27).
// Lazy (app.js, LAZY_MODULES.extraNotice). The one builder of that notice; a
// surface calls `extraNoticeMount(host, id)` where the feature is used. The
// recipe is the no-model notice's (DESIGN.md, "A notice that can be closed"):
// icon, one sentence, an Install button, a close last. It shows while the
// package is missing, and a dismissal lasts until that package's state
// changes: seen installed, the dismissal is forgotten, so an uninstall brings
// the notice back.
(() => {
  const DISMISSED_KEY = "tessellate-extra-notice-dismissed";
  //: One sentence per package in the registry (`core/extras.py`), plus SearXNG,
  //: which has its own installer. Sentence case, under 90 characters.
  const EXTRA_NOTICE_WHAT = {
    pdfpages: "Opening scanned PDF pages needs the PDF pages package.",
    voice: "Voice notes need the voice package.",
    desktop: "The desktop window needs the desktop package.",
    semantic: "Search by meaning needs the meaning package.",
    documents: "Importing documents needs the documents package.",
    ocr: "Reading text in images needs Tesseract.",
    rapidocr: "Reading text in images needs an OCR package.",
    pyodide: "Running Python files needs the Python runner.",
    languagetool: "Grammar checks need the LanguageTool package.",
    needle: "Local tool calls need the Needle package.",
    translate: "Translating offline needs the translate package.",
    localllm: "A built-in model needs the local model package.",
    captions: "Live captions need the captions package.",
    searxng: "Private web search needs SearXNG, which is not installed.",
  };
  let cache = { at: 0, rows: null };

  //: Kept in `prefs` (localStorage), so a dismissal outlives the session.
  function dismissedList() {
    const saved = prefs.json(DISMISSED_KEY, []);
    return Array.isArray(saved) ? saved : [];
  }
  const saveDismissed = (list) => prefs.setJSON(DISMISSED_KEY, list);
  const dismissed = (id) => dismissedList().includes(id);
  const dismiss = (id) => dismissed(id) || saveDismissed([...dismissedList(), id]);
  const forget = (id) => dismissed(id) && saveDismissed(dismissedList().filter((one) => one !== id));

  //: `GET /extras` once per few seconds however many notices ask.
  async function extraRows(fresh = false) {
    if (!fresh && cache.rows && Date.now() - cache.at < 3000) return cache.rows;
    const body = await apiJson("/extras", { silent: true }).catch(() => null);
    cache = { at: Date.now(), rows: body ? body.extras : null };
    return cache.rows;
  }

  //: `{ missing, row }`: whether the package is absent, and what the server says of it.
  async function extraNoticeState(id, fresh = false) {
    if (id === "searxng") {
      const info = await apiJson("/websearch/searxng/status", { silent: true }).catch(() => null);
      //: No backend (no Docker, no virtualenv) is Settings' to explain, not an install.
      return { missing: Boolean(info && info.backend && info.state === "absent" && !info.installing), row: null };
    }
    const row = ((await extraRows(fresh)) || []).find((one) => one.id === id);
    return { missing: Boolean(row && !row.installed), row: row || null };
  }

  async function extraNoticeInstall(id, row) {
    if (id === "searxng") {
      const result = await apiJson("/websearch/searxng/start", { method: "POST" }).catch((error) => ({ error: error.message }));
      if (result.error) toast(result.error, "info", { action: ["Open Settings", () => openSettingsModal("websearch")] });
      else toast("SearXNG is installing. Settings, Web search shows its progress.", "info");
      return;
    }
    if (!(await confirmDialog(`Install ${row.label}?\n\nAbout ${row.size.replace(/^~/, "")} is downloaded from ${row.source}. It runs on this computer.`))) return;
    const result = await apiJson(`/extras/${id}/install`, { method: "POST" }).catch((error) => ({ started: false, message: error.message }));
    if (!result.started) return toast(result.message || "The install could not start.", "info", { action: ["Open Packages", () => openSettingsModal("extras")] });
    toast(`Installing ${row.label}.`, "info");
    for (let waited = 0; waited < 600; waited += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const body = await apiJson("/extras", { silent: true }).catch(() => null);
      if (body && !body.running) break;
    }
  }

  //: Draws or clears `host`. Seen present: the dismissal is forgotten first, so
  //: the notice returns if the package is removed later.
  async function extraNoticeCheck(host, id, fresh = false) {
    const { missing, row } = await extraNoticeState(id, fresh);
    if (!missing) forget(id);
    const show = missing && !dismissed(id);
    host.replaceChildren();
    host.classList.toggle("hidden", !show);
    if (!show) return;
    setLabel(host, "ph:package");
    const text = document.createElement("span");
    text.className = "ai-offline-text";
    text.textContent = EXTRA_NOTICE_WHAT[id];
    const install = document.createElement("button");
    install.type = "button";
    install.className = "ghost small";
    const manual = Boolean(row && row.unavailable);
    install.textContent = manual ? "Open Packages" : "Install";
    install.title = manual ? row.unavailable : `Installs it from Settings, Packages${row ? `: ${row.enables}` : ""}`;
    install.addEventListener("click", async () => {
      if (manual) return openSettingsModal("extras");
      install.disabled = true;
      await extraNoticeInstall(id, row);
      extraNoticeCheck(host, id, true);
    });
    host.append(text, install);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "ghost small icon-only";
    close.dataset.dismiss = "notice";
    setLabel(close, "ph:x");
    close.title = "Hide this until the package is installed or removed";
    close.setAttribute("aria-label", "Hide this notice until the package is installed or removed");
    close.addEventListener("click", () => {
      dismiss(id);
      host.replaceChildren();
      host.classList.add("hidden");
    });
    host.append(close);
  }

  //: Puts the notice as the first child of `parent` (one per package there) and
  //: checks it. Safe to call on every open of the feature.
  function extraNoticeMount(parent, id, { fresh = false } = {}) {
    if (!parent || !EXTRA_NOTICE_WHAT[id]) return Promise.resolve();
    let host = parent.querySelector(`:scope > .extra-notice[data-extra="${id}"]`);
    if (!host) {
      host = document.createElement("div");
      host.className = "notice extra-notice hidden";
      host.dataset.extra = id;
      host.setAttribute("role", "status");
      parent.prepend(host);
    }
    return extraNoticeCheck(host, id, fresh);
  }

  Object.assign(window, { extraNoticeMount });
})();
