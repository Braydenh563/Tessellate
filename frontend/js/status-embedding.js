// status-embedding.js: the once-per-problem notice for a broken search engine (`nudgeEmbeddingProblem`).
// Moved out of status.js (LEDGER L698, L639) to come off the boot file: lazy, the `statusEmbedding` bundle
// with a stand-in in lazy-entries.js. Nobody reads a return value; `renderAiPill` calls it on a poll tick
// that already carries `embedding_error`, so the first load rides that tick.

//: packaged app: "I didnt have sentence transformers installed ... I
//: encountered errors and I saw no popup or anything to suggest that I
//: switch to nomic-embed-text or install sentence transformers"). The fix
//: sentence and its one-click button lived only in Settings, Models, which
//: nobody opens to find out why search feels dull. So the first poll that
//: carries `embedding_error` raises a toast with the way to fix it and leaves
//: the same in the bell, keyed by the error so it is said once per problem,
//: not once per poll.
let embeddingNudgeSaid = "";

function embeddingProblemDetail(error) {
  return `${withoutEndStop(error)}. Settings, Models can switch it to ${EMBEDDING_FALLBACK_MODEL} or install the package.`;
}

//: The toast is once per browser session (X24); the bell keeps every problem.
//: Blocked storage falls back to `embeddingNudgeSaid`: once per page load.
function embeddingToastDue() {
  try {
    if (sessionStorage.getItem("embeddingToastShown")) return false;
    sessionStorage.setItem("embeddingToastShown", "1");
  } catch {
    // No storage: the in-memory once-per-problem guard above still holds.
  }
  return true;
}

function nudgeEmbeddingProblem() {
  const error = modelStatus?.embedding_error;
  if (!error || modelStatus.semantic_off || error === embeddingNudgeSaid) return;
  embeddingNudgeSaid = error;
  const installing = /being installed/.test(error);
  const title = installing ? "Search by meaning is being installed" : "Search by meaning is not working";
  const detail = installing
    ? "Search uses keywords until it finishes. Or pick nomic-embed-text in Settings, Models."
    : embeddingProblemDetail(error);
  recordNotification({
    kind: "assist",
    title,
    detail,
    key: `embedding:${error}`,
    action: { settings: "models" },
  });
  //: While the download question is up it already says keywords work
  //: meanwhile: a second toast said it again, stacked over Settings (audit 1028 E40).
  if (!installing && !modelStatus.semantic_offer && embeddingToastDue()) toastAction(`${title}. Search is using keywords for now.`, "Fix it", () => openSettingsModal("searchindex", "embedding-model-select"), { record: false });
}
