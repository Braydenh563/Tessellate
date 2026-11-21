// model-spec.js: the Models screen's spec list, context window box and health note. Lazy: loaded by the
// renderModelSpec stand-in (it carries `.run`) in chat-model-panel.js, so the boot bytes do not carry a screen most sessions never open.

(() => {
function renderModelContextBox(modelName, spec) {
  const box = $("model-context-window");
  const note = $("model-context-note");
  if (!box) return;
  modelContextModel = modelName || "";
  const windows = (prefsCache && prefsCache.model_context_windows) || {};
  const set = Number(windows[modelContextModel]);
  //: Not `box.value = set || ""`: a stored 0 is not a window, and writing "0"
  //: into the box would show a number that means auto, which is the one thing
  //: this control must never do.
  box.value = set > 0 ? String(set) : "";
  box.disabled = !modelContextModel;
  const usable = spec && spec.usable_context;
  //: B56: the empty box says what Auto found, not only the word.
  box.placeholder = usable ? `Auto (${Number(usable).toLocaleString()})` : "Auto";
  if (!note) return;
  if (!modelContextModel) {
    note.textContent = "";
    return;
  }
  //: The note says what is actually in force, which is the only way to tell
  //: "auto found 32k" apart from "auto fell back to 4k", and those look
  //: identical in an empty box.
  note.textContent = set > 0
    ? `Running ${modelContextModel} at ${set.toLocaleString()} tokens. Clear the box for auto.`
    : spec && spec.context_reason
      ? `Auto: ${spec.context_reason}`
      : usable
      ? `Auto: ${Number(usable).toLocaleString()} tokens, from the model.`
      : "Auto: the app uses the model's own window.";
}

renderModelSpec.run = async function (modelName) {
  const box = $("model-spec");
  if (!box) return;
  const spec = await apiJson(`/models/spec?name=${encodeURIComponent(modelName || "")}`, {
    silent: true,
  }).catch(() => null);
  if (!spec) {
    box.classList.add("hidden");
    renderModelContextBox(modelName, null);
    return;
  }
  renderModelContextBox(modelName, spec);
  // Tri-state, and the third state is the point: null means "this backend
  // doesn't report capabilities", which is not the same as "no". Saying "no"
  // about a model that works fine would send someone chasing a problem that
  // isn't there.
  // `== null`, not `=== null`: the whole point of this helper is that "not
  // declared" must never render as a confident "no" (§35C), and a *missing*
  // key is exactly as unknown as an explicit null. With `===` an absent field
  // fell through to the falsy branch and printed "no", the reported bug,
  // surviving in the one case nobody checked.
  const canDo = (value) => (value == null ? "not reported" : value ? "yes" : "no");
  const rows = [
    ["Size", spec.parameters],
    ["Quantisation", spec.quantisation],
    ["Family", spec.family],
    // Two windows, deliberately. A 128k model is *run* at less because the KV
    // cache scales with the window, without both numbers the percentage on
    // each message looks wrong to anyone who knows what the model can hold.
    [
      "Reads at once",
      spec.context_length
        ? `${compactTokens(spec.usable_context)} tokens` +
          (spec.context_length > spec.usable_context
            ? ` (it can hold ${compactTokens(spec.context_length)})`
            : "")
        : null,
    ],
    ["Loaded at", spec.loaded_context_length ? compactTokens(spec.loaded_context_length) : null],
    ["Can use tools", canDo(spec.supports_tools)],
    // "Can think: no" was reported for a model that visibly thinks (§35C),
    // and the label was the lie rather than the value: this is the *declared*
    // capability, whether the backend supports a thinking toggle, and a
    // model can still emit inline <think> tags without declaring it, which
    // `split_thinking` picks up and shows. Saying "declared" makes the two
    // facts distinguishable instead of contradictory.
    ["Thinking switch", canDo(spec.supports_thinking)],
    ["Can see images", canDo(spec.supports_vision)],
  ].filter(([, value]) => value != null && value !== "");

  box.replaceChildren();
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    box.append(dt, dd);
  }
  box.classList.toggle("hidden", rows.length === 0);

  renderModelHealthNote(spec);
};

// A model health card: every number above already existed, but nothing said
// what it *means*: "this model has an 8k window" doesn't answer "will it
// forget what I said earlier in a long chat" (BACKLOG.md §95 item A.2).
// Mirrors ai/context.py's own shares (CHARS_PER_TOKEN, OUTPUT_RESERVE_SHARE,
// HISTORY_SHARE) rather than asking the backend, since this is explicitly a
// rough estimate: context.py's own docstring: "approximately right on every
// model beats being exactly right on one", and an average exchange length
// is itself a guess, so a precise-looking number here would be a false
// promise the actual conversation could contradict either way.
function renderModelHealthNote(spec) {
  const note = $("model-spec-health");
  if (!note) return;
  const usable = spec && spec.usable_context;
  if (!usable) {
    note.classList.add("hidden");
    return;
  }
  const CHARS_PER_TOKEN = 4;
  const OUTPUT_RESERVE_SHARE = 0.15;
  const HISTORY_SHARE = 0.15;
  const AVG_CHARS_PER_EXCHANGE = 500; // a short question + a real answer
  const historyChars =
    usable * CHARS_PER_TOKEN * (1 - OUTPUT_RESERVE_SHARE) * HISTORY_SHARE;
  const roughTurns = Math.round(historyChars / AVG_CHARS_PER_EXCHANGE / 5) * 5;

  if (roughTurns < 5) {
    note.textContent =
      "A small window: a back-and-forth chat will start losing earlier messages within a few exchanges. Notes and documents are unaffected; only the conversation itself is short-lived.";
  } else if (roughTurns <= 40) {
    note.textContent = `What this means for you: a long chat will start dropping its earliest messages after roughly ${roughTurns} exchanges. Atlas can still recall anything from further back by re-reading the note or asking again, it just won't be sitting in view.`;
  } else {
    note.textContent =
      "A large window: a normal conversation is very unlikely to ever run out of room.";
  }
  note.classList.remove("hidden");
}
})();
