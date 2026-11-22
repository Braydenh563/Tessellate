// status-settings.js: the Settings pane's model-status draw (`renderSettings`, its Background tasks and Search and
// index halves). Moved out of status.js (LEDGER L-world-class-631) to come off the boot file: lazy, the
// `statusSettings` bundle with a stand-in in lazy-entries.js. Nobody reads a return value, and it draws only
// while Settings is open or being opened (status.js's poll, settings.js after its refresh).

function renderSettings() {
  const status = modelStatus;
  const ollamaLine = $("ollama-status");

  //: **Only "can't reach" when it cannot** (INBOX 435): this said the
  //: app's server was unreachable while the app was plainly running, on a
  //: first open before the status had answered and whenever a slow model
  //: server ran the poll past its budget.
  if (!status) {
    ollamaLine.textContent =
      {
        slow: "The model server is slow to answer. Checking again…",
        error: "Couldn't read the models' status. Checking again…",
        down: "Can't reach the Tessellate server.",
      }[modelStatusProblem] || "Checking the models…";
    ollamaLine.className = `status ${modelStatusProblem === "down" ? "off" : "is-checking"}`;
    //: The pane's shape under the line while it waits, never the line alone
    //: (DESIGN.md's list recipe). Not when the answer is a fault: a skeleton
    //: says "on its way", and "can't reach" is not that.
    if (modelStatusProblem === "down") clearSkeletons($("models-skeleton"));
    else showSkeletons($("models-skeleton"), 2);
    if (!modelStatusProblem) refreshModelStatus().then(() => settingsOpen() && renderSettings());
    return;
  }
  clearSkeletons($("models-skeleton"));

  // Name the backend that actually answered. Saying "Ollama not detected"
  // when the app was pointed at LM Studio sends people to install the wrong
  // thing (§6).
  const backend = status?.provider === "openai" ? "The model server" : "Ollama";
  //: The dot is the line's class, as on the search engine line under it,
  //: not a typed "●"/"○" beside a CSS dot: two alphabets for one signal.
  //: Section 21 row 12: an address the person typed that nothing answers is
  //: a different problem from a server that is not started, and says so.
  ollamaLine.textContent = status.ollama_running
    ? `${backend} is running`
    : status.unreachable_hint || `${backend} isn't running`;
  ollamaLine.className = `status ${status.ollama_running ? "ok" : status.ollama_busy ? "is-checking" : "off"}`;
  //: With no model server running, the two optional ways to run a model here
  //: (extra-notice.js). Drawn when the answer changes, not on every poll.
  const noServer = !status.ollama_running && !status.ollama_busy;
  if (ollamaLine.dataset.noServer !== String(noServer)) {
    ollamaLine.dataset.noServer = String(noServer);
    for (const id of ["needle", "localllm"]) {
      if (noServer) extraNoticeMount($(`xn-${id}`), id);
      else $(`xn-${id}`)?.replaceChildren();
    }
  }
  //: A slow poll keeps the last answer on screen (see refreshModelStatus), so
  //: the line says so instead of presenting a stale answer as fresh.
  if (modelStatusProblem === "slow") {
    ollamaLine.textContent = "The model server is slow to answer. Showing the last answer.";
    ollamaLine.className = "status is-checking";
  }
  //: K13: with no model, the line says what answers instead (ai/composer.py).
  if (aiIsOff()) {
    ollamaLine.title = "Until a model is connected, Atlas answers with its built-in composer: from your notes, no AI.";
  } else ollamaLine.title = "";
  renderBackendPicker(status);
  //: The one-time question before search by meaning is downloaded
  //: (semantic-notice.js, lazy): opened while the server says it is owed,
  //: closed once it is answered.
  if (status.semantic_offer || lazyModuleLoads.has("semanticNotice")) semanticOffer(Boolean(status.semantic_offer), status.semantic_engine_moved);
  //: Search and index's half is drawn with that pane, now when it is built and at its build if not (L675).
  onSurface("settings-searchindex", renderSettings.index);
  // The "install Ollama" advice only helps someone who chose Ollama.
  $("ollama-help").classList.toggle(
    "hidden",
    status.ollama_running || status.provider !== "ollama"
  );
  $("models-config").classList.toggle("hidden", !status.ollama_running);
  // Downloads are an Ollama capability. Every other backend is handed a model
  // that is already on disk, so the panel hides rather than offering a button
  // that cannot work. With Ollama simply not running (audit 1028 E38) the
  // cards stay: choosing a model for this computer needs no backend, and
  // each Download waits with the reason on it.
  $("suggested-box").classList.toggle("hidden", status.supports_pull === false);

  //: Always, not only while a backend answers: the rows come from saved
  //: settings, and a person with the server down still needs to see and clear
  //: an override (WORLD_CLASS_PLAN 20, built).
  renderFeatureModels(status);
  settingsReadouts.smallModel?.();
  if (status.ollama_running) {
    renderChatModelPicker(status);
    renderUtilityModelPicker(status);
    renderVisionModelPicker(status);
  renderOcrModelPicker(status);
    //: Background tasks' picker, with that pane (L675).
    onSurface("settings-tasks", renderSettings.tasks);
    //: Both live in the lazy `settingsUi` file: one check that it has loaded
    //: covers the two (it has whenever Settings is open, the only time this runs).
    if (typeof renderSuggested === "function") {
      renderInstalledModels(status);
      renderSuggested(status);
    }
    renderModelSpec(status.chat_model);
  } else {
    $("installed-box").classList.add("hidden");
    $("model-spec").classList.add("hidden");
    $("model-spec-health").classList.add("hidden");
    //: The cards draw with no backend too (audit 1028 E38): what fits this
    //: computer needs none. `window.` because the file is lazy, as above.
    if (status.supports_pull !== false) window.renderSuggested?.(status);
  }
}

renderSettings.tasks = () => modelStatus?.ollama_running && renderAutonomousModelPicker(modelStatus);

//: The search engine's picker, the reindex box, the engine's error line and its one-click fix, in Search and index.
renderSettings.index = () => {
  const status = modelStatus;
  if (!status) return;
  // The search engine is always adjustable: its recommended option is the
  // built-in one, which needs no Ollama. Only the Ollama half of it depends
  // on Ollama being up.
  if (typeof renderEmbeddingPicker === "function") renderEmbeddingPicker(status);
  renderReindex(status);
  const embeddingError = $("embedding-error");
  embeddingError.classList.toggle("hidden", !status.embedding_error);
  //: A missing optional package arrives as a sentence the backend wrote for
  //: people ("Search by meaning is being installed..."), not an exception, so
  //: it is shown as it is with the one alternative that needs no install: an
  //: Ollama embedding model. Said even when Ollama is not running, because
  //: the owner's report was exactly that case ("no nomic-embed-text
  //: suggested") and the button below only exists while it is.
  //: The notice recipe's icon first (section 21 rows 1 and 2), then the line.
  embeddingError.title = "";
  const say = (text) => setLabel(embeddingError, `ph:warning ${text}`);
  if (status.embedding_error && /^Search by meaning/.test(status.embedding_error)) {
    say(`${withoutEndStop(status.embedding_error)}.`);
    embeddingError.title = `Or ${status.ollama_running ? "" : "start Ollama and "}pick ${EMBEDDING_FALLBACK_MODEL} as the search engine: smaller, and offline.`;
  } else if (status.embedding_error) {
    say(
      `Search engine problem: ${status.embedding_error}: semantic search is ` +
      "falling back to keywords. Quick fix: switch the search engine below to " +
      "an Ollama embedding model (download nomic-embed-text from the list), " +
      "it runs fully offline. Full details in Settings, Logs."
    );
  }
  // The one-click version of the "quick fix" sentence above: only offered
  // when it can actually be carried out (Ollama has to be running to either
  // pull or use an Ollama embedding model), and not while the fix is
  // already running or already switched over.
  const fixRow = $("embedding-error-fix-row");
  const alreadyOnOllama = status.embedding_backend === "ollama"
    && status.embedding_model === EMBEDDING_FALLBACK_MODEL;
  fixRow.classList.toggle(
    "hidden",
    !status.embedding_error
      || !status.ollama_running
      || !status.supports_pull
      || embeddingFallbackRunning
      || alreadyOnOllama
  );
  stagePrimary("embedding-apply", "embedding-error-fix", !fixRow.classList.contains("hidden"));
  renderSearchEngineHealth(status);
};
