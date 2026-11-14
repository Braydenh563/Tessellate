// extra-notice.js: "this feature needs an optional package" (INBOX 1748, Q27).
// Lazy (app.js, LAZY_MODULES.extraNotice). The one builder of that notice; a
// surface calls `extraNoticeMount(host, id)` where the feature is used. The
// recipe is the no-model notice's (DESIGN.md, "A notice that can be closed"):
// icon, one sentence, an Install button, a close last. It shows while the
// package is missing, and a dismissal lasts until that package's state
// changes: seen installed, the dismissal is forgotten, so an uninstall brings
// the notice back.
//
// **The button turns to Undo once pressed** (the owner, 2026-11-11: "turns to
// an undo if pressed"). The Install click is the consent, so there is no
// dialog. While the install runs the same button is Undo and stops the
// download (`POST /tasks/cancel`, kind "extra"); once it has landed the notice
// stays, says so, and Undo removes the package again (`POST
// /extras/{id}/uninstall`). SearXNG has no uninstall: its Undo stops it.
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
    rapidocr: "RapidOCR is the quickest way to read text in images.",
    pyodide: "Running Python files needs the Python runner.",
    languagetool: "Grammar checks need the LanguageTool package.",
    "spell-fr": "Spelling for French needs the French spelling pack.",
    "spell-de": "Spelling for German needs the German spelling pack.",
    "spell-es": "Spelling for Spanish needs the Spanish spelling pack.",
    needle: "Local tool calls need the Needle package.",
    translate: "Translating offline needs the translate package.",
    localllm: "A built-in model needs the local model package.",
    captions: "Live captions need the captions package.",
    captionmodel: "Live captions need the captions model.",
    naturalvoice: "Read aloud in a natural voice needs the voice engine.",
    "naturalvoice-voice": "Read aloud in a natural voice needs the voice file.",
    speakers: "Labelling who speaks needs the speaker packages.",
    speakermodels: "Telling voices apart needs the two speaker models.",
    ruff: "Checking Python files for mistakes needs Ruff.",
    searxng: "Private web search needs SearXNG, which is not installed.",
  };
  let cache = { at: 0, rows: null };
  //: Packages this session pressed Install on: id -> "installing" | "installed".
  //: What turns the button to Undo, and what keeps a finished notice on screen.
  const pressed = new Map();

  //: Kept in `prefs` (localStorage), so a dismissal outlives the session.
  function dismissedList() {
    const saved = prefs.json(DISMISSED_KEY, []);
    return Array.isArray(saved) ? saved : [];
  }
  const saveDismissed = (list) => prefs.setJSON(DISMISSED_KEY, list);
  const dismissed = (id) => dismissedList().includes(id);
  const dismiss = (id) => dismissed(id) || saveDismissed([...dismissedList(), id]);
  const forget = (id) => dismissed(id) && saveDismissed(dismissedList().filter((one) => one !== id));

  //: `GET /extras` once per few seconds however many notices ask. The cache here holds only finished
  //: answers, so two notices asking in the same tick both fetched (measured at the Settings open);
  //: `cacheMs` makes the second share the first's request.
  async function extraRows(fresh = false) {
    if (!fresh && cache.rows && Date.now() - cache.at < 3000) return cache.rows;
    const body = await apiJson("/extras", { silent: true, ...(fresh ? {} : { cacheMs: 3000 }) }).catch(() => null);
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
    const rows = (await extraRows(fresh)) || [];
    //: Speaker labels are two packages (the engine and its models) installed as one bundle: missing when either is.
    if (id === "speakers") {
      const engine = rows.find((one) => one.id === "speakers");
      const models = rows.find((one) => one.id === "speakermodels");
      if (!engine || !models) return { missing: false, row: null };
      return { missing: !(engine.installed && models.installed), row: { ...engine, label: "Speaker labels", size: "about 40 MB", source: "pypi.org and github.com" } };
    }
    const row = rows.find((one) => one.id === id);
    return { missing: Boolean(row && !row.installed), row: row || null };
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  //: Waits for the one install lane to be free (`GET /extras` `running`).
  async function extraNoticeWaitIdle() {
    for (let waited = 0; waited < 600; waited += 1) {
      await sleep(1500);
      const body = await apiJson("/extras", { silent: true }).catch(() => null);
      if (body && !body.running) return;
    }
  }

  //: Starts the install. The click was the consent, so nothing is asked first.
  //: Returns whether it started; the caller waits and repaints.
  async function extraNoticeInstall(id) {
    if (id === "searxng") {
      await ensureModule("webClip");
      const result = await startSearxng(true, () => {}).catch((error) => ({ error: error.message }));
      if (result.error) toast(result.error, "info", { action: ["Open Settings", () => openSettingsModal("websearch")] });
      else toast("SearXNG is installing. Settings, Web search shows its progress.", "info");
      return !result.error;
    }
    //: Speaker labels need the engine and its models: one click installs the bundle.
    const asked = id === "speakers" ? apiJson("/extras/bulk", { method: "POST", body: JSON.stringify({ action: "install", bundle: "speakers" }) }) : apiJson(`/extras/${id}/install`, { method: "POST" });
    const result = await asked.catch((error) => ({ started: false, message: error.message }));
    if (!result.started) {
      toast(result.message || "The install could not start.", "info", { action: ["Open Packages", () => openSettingsModal("extras")] });
      return false;
    }
    toast("Installing. Undo on the notice stops it.", "info");
    return true;
  }

  //: Undo. While installing it stops the download; once installed it removes
  //: the package. The caller repaints from the server's answer afterwards.
  async function extraNoticeUndo(id, phase) {
    if (id === "searxng") {
      await apiJson("/websearch/searxng/stop", { method: "POST" }).catch((error) => toast(error.message, "info"));
      return;
    }
    if (phase === "installing") {
      const body = await apiJson("/tasks/cancel", { method: "POST", body: JSON.stringify({ kind: "extra", name: id }) }).catch(() => ({ detail: "Couldn't stop the install. Try again." }));
      toast(body?.detail || "Stopping the install.", "info");
      return;
    }
    const asked = id === "speakers" ? apiJson("/extras/bulk", { method: "POST", body: JSON.stringify({ action: "uninstall", bundle: "speakers" }) }) : apiJson(`/extras/${id}/uninstall`, { method: "POST" });
    const result = await asked.catch((error) => ({ started: false, message: error.message }));
    if (!result.started) return toast(result.message || "It could not be removed.", "info", { action: ["Open Packages", () => openSettingsModal("extras")] });
    await extraNoticeWaitIdle();
  }

  //: Draws or clears `host`. Seen present: the dismissal is forgotten first, so
  //: the notice returns if the package is removed later. `needed` is false
  //: where the feature has another way to work (a vision model reads pages):
  //: the notice then shows only for an install this session started.
  async function extraNoticeCheck(host, id, fresh = false, needed = true) {
    const { missing, row } = await extraNoticeState(id, fresh);
    if (!missing) forget(id);
    let phase = pressed.get(id) || "";
    //: Pressed, but it did not land (stopped, failed) or was removed elsewhere.
    if (phase === "installed" && missing && id !== "searxng") phase = "";
    if (phase === "installing" && !missing && !row?.installing && id !== "searxng") phase = "installed";
    if (phase) pressed.set(id, phase);
    else pressed.delete(id);
    const show = Boolean(phase) || (missing && needed && !dismissed(id));
    host.replaceChildren();
    host.classList.toggle("hidden", !show);
    if (!show) return;
    setLabel(host, "ph:package");
    const text = document.createElement("span");
    text.className = "ai-offline-text";
    if (phase === "installing") text.textContent = id === "searxng" ? "Setting SearXNG up." : "Installing…";
    else if (phase === "installed") text.textContent = id === "searxng" ? "SearXNG is on. Undo stops it." : "Installed. Undo removes it.";
    else text.textContent = EXTRA_NOTICE_WHAT[id];
    const install = document.createElement("button");
    install.type = "button";
    install.className = "ghost small";
    const manual = Boolean(row && row.unavailable);
    if (phase) {
      install.textContent = "Undo";
      install.dataset.extraUndo = phase;
      install.title = phase === "installing" ? "Stops the download and removes what it fetched." : id === "searxng" ? "Stops SearXNG." : "Removes the package again.";
    } else {
      install.textContent = manual ? "Open Packages" : "Install";
      install.title = manual ? row.unavailable : `Installs it from Settings, Packages.${row ? ` ${row.enables}` : ""}`;
    }
    install.addEventListener("click", async () => {
      if (phase) {
        install.disabled = true;
        await extraNoticeUndo(id, phase);
        window.dispatchEvent(new CustomEvent("tessellate:extras-changed", { detail: { id } }));
        //: A removal is over here; a stopped install repaints from its own wait.
        if (phase === "installed") pressed.delete(id);
        return phase === "installed" ? extraNoticeCheck(host, id, true, needed) : undefined;
      }
      if (manual) return openSettingsModal("extras");
      pressed.set(id, "installing");
      install.disabled = true;
      const started = await extraNoticeInstall(id);
      if (!started) {
        pressed.delete(id);
        return extraNoticeCheck(host, id, true, needed);
      }
      extraNoticeCheck(host, id, true, needed);
      if (id !== "searxng") await extraNoticeWaitIdle();
      const after = await extraNoticeState(id, true);
      if (id === "searxng" || !after.missing) pressed.set(id, "installed");
      else pressed.delete(id);
      //: Tells a surface that read the package's state (the spelling packs) to ask again.
      window.dispatchEvent(new CustomEvent("tessellate:extras-changed", { detail: { id } }));
      extraNoticeCheck(host, id, true, needed);
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
      //: Closing a finished install ends its Undo; it is not a "never ask".
      if (phase === "installed") pressed.delete(id);
      else if (!phase) dismiss(id);
      host.replaceChildren();
      host.classList.add("hidden");
    });
    host.append(close);
  }

  //: Puts the notice as the first child of `parent` (one per package there) and
  //: checks it. Safe to call on every open of the feature.
  function extraNoticeMount(parent, id, { fresh = false, needed = true } = {}) {
    if (!parent || !EXTRA_NOTICE_WHAT[id]) return Promise.resolve();
    let host = parent.querySelector(`:scope > .extra-notice[data-extra="${id}"]`);
    if (!host) {
      host = document.createElement("div");
      host.className = "notice extra-notice hidden";
      host.dataset.extra = id;
      host.setAttribute("role", "status");
      parent.prepend(host);
    }
    return extraNoticeCheck(host, id, fresh, needed);
  }

  Object.assign(window, { extraNoticeMount });
})();
