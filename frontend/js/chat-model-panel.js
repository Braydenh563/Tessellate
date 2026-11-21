// chat-model-panel.js: model spec and health, response modes, persona, usage, context meter, turn count. A classic script sharing the page globals, split out of chat.js (L-world-class-770); loaded right after it.

// What the backend says about the model in use. Fetched when the Models
// screen is drawn rather than polled: none of it changes while the app runs.
//: **The context window, per model, set by hand.**
//:
//: Asked for (INBOX 77): "the window itself should be manageable by the user
//: and auto when set ... a `num_ctx` preference per model in Settings, Models
//: with Auto (the model file's value) or a number, sent on every request; the
//: badge shows 'used / window'". The badge half shipped first; this is the
//: window half.
//:
//: The box edits whichever chat model is selected and the app stores one entry
//: per model (`model_context_windows` in preferences), so switching models
//: switches what the box says rather than carrying one machine-wide number
//: across a 4k model and a 32k one. Empty is auto, which is stored as the
//: absence of a number: `usable_context` in provider.py then reads the window
//: from the model file or the server's catalog exactly as it always has.
//:
//: **Saved on change and on blur, not on a Save button**, because this screen
//: has no Save button and every other control on it writes as you touch it. A
//: number box fires `change` when it is committed (Enter, or focus leaving),
//: which is the event that means "I meant that", and `input` would PUT once
//: per keystroke while somebody types 16384.
let modelContextModel = "";

//: Stand-in: the spec list, window box and health note live in the lazy model-spec.js.
function renderModelSpec(modelName) {
  return lazyScript("/js/model-spec.js").then(() => renderModelSpec.run(modelName));
}

// Both pickers for the response preset: the Chat toolbar's and the Notes
// quick-ask box's. Two controls, one stored preference, the quick-ask box
// always obeyed the saved mode and simply had no way to set it, so this is a
// second way in rather than a second setting. Listed rather than found by
// class so a stray `.small-select` can never join by accident.
const RESPONSE_MODE_SELECTS = ["response-mode-select", "ask-mode-select"];

// The response presets, fetched once. Served by /chat/modes rather than
// listed here so adding a fourth is a change to `ai/presets.py` alone (§11).
//: The answer is read once and painted again when the Chat pane is built.
const loadResponseModes = (() => {
  let body = null;
  const paint = () => {
    const selects = RESPONSE_MODE_SELECTS.map((id) => document.getElementById(id)).filter(Boolean);
    if (!selects.length || !body || !body.modes) return;
    const active = body.modes.find((m) => m.id === body.active);
    for (const select of selects) {
      select.replaceChildren();
      for (const mode of body.modes) {
        const option = document.createElement("option");
        option.value = mode.id;
        option.textContent = mode.label;
        option.title = mode.description;
        if (mode.id === body.active) option.selected = true;
        select.appendChild(option);
      }
      if (active) select.title = active.description;
    }
  };
  onSurface("chat", paint);
  return async () => {
    body = await apiJson("/chat/modes", { silent: true }).catch(() => null);
    paint();
  };
})();

// Picking in one picker moves the other. Without this the two would drift
// apart the moment either was touched, and the one you weren't looking at
// would be lying about what the next answer will do.
async function setResponseMode(chosen) {
  for (const id of RESPONSE_MODE_SELECTS) {
    const select = $(id);
    if (!select) continue;
    select.value = chosen;
    const option = select.selectedOptions[0];
    select.title = (option && option.title) || "";
  }
  // Changing the picker changes the default too, otherwise someone who works
  // in Quick would re-pick it on every reload. The *request* still carries the
  // mode per turn, so this is "remember what I chose" rather than a second
  // setting that can disagree with the dropdown.
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ response_mode: chosen }),
  }).catch(() => {});
}

//: A persona's mark into its holder: the generated face for every persona
//: but the app's own voice, which keeps the app's emblem. Shared by the
//: persona rows in Settings and the chat's persona picker, so the two
//: cannot draw one persona two ways.
function fillPersonaMark(holder, name, size = 20) {
  if (!holder) return;
  //: Nothing to draw a face from (no name yet): the app's own animated mark,
  //: never an empty box (the owner: "the default for no avatar selected
  //: should be the animated app logo everywhere").
  if (!name) {
    renderEmblem(holder, size, { animate: true });
    return;
  }
  //: Atlas has a face of its own now (`atlasMark`, avatars.js): the logo's
  //: ring of linked notes orbiting a globe in the accent colour. `nameMark`
  //: draws it for the assistant's name. The chat's reply label keeps the
  //: live logo, so the app's mark and Atlas's face both stay in the app.
  //: The faces arrive after the page (`afterCharacters`, lazy-entries.js).
  afterCharacters(() => holder.replaceChildren(nameMark(name === aiNameNow() ? "Atlas" : name, size)), () => plainHead(holder, name));
}

function personaOptions() {
  // Built-ins + the user's custom personas (deduped: an edited built-in
  // is stored under the same name); the active one pre-selected.
  const select = $("persona-select");
  const custom = (prefsCache && prefsCache.personas) || [];
  const active = personaDisplayName(prefsCache && prefsCache.active_persona);
  const names = [
    ...new Set([aiNameNow(), "Coach", "Analyst", ...custom.map((p) => p.name)]),
  ];
  // name -> its prompt, so the dropdown can describe each persona on hover.
  const overrides = new Map(custom.map((p) => [p.name, p]));
  const describe = (name) => {
    const prompt = (overrides.get(name) || {}).prompt || builtinPersonas()[name] || "";
    return prompt.length > 200 ? prompt.slice(0, 199) + "…" : prompt;
  };
  select.replaceChildren();
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    option.title = describe(name); // hover shows what this persona does
    if (name === active) option.selected = true;
    select.appendChild(option);
  }
  // Also surface the active persona's description on the closed select itself.
  //: While no model runs the gate (`syncModelGatedControls`) has put the reason
  //: in the title; the description waits in `enabledTitle` for its return.
  if (select.dataset.enabledTitle !== undefined) select.dataset.enabledTitle = describe(active);
  else select.title = describe(active);
  // The full prompt, not the hover excerpt: the preview panel exists precisely so
  // the instructions the model is given aren't a 200-character preview.
  const fullPrompt = (name) =>
    (overrides.get(name) || {}).prompt || builtinPersonas()[name] || "";
  //: The preview shows the text the model gets, so `{ai_name}` is filled
  //: here the way `librarian.fill_ai_name` fills it on the server.
  const showPrompt = (name) => {
    $("persona-prompt-text").textContent =
      fullPrompt(name).replaceAll("{ai_name}", aiNameNow()) || "This persona adds no instructions of its own.";
  };
  showPrompt(active);
  //: A native select cannot draw a picture in an option, so the chosen
  //: persona's mark sits beside it and follows the choice.
  fillPersonaMark($("persona-select-mark"), select.value);
  select.onchange = () => {
    if (select.dataset.enabledTitle !== undefined) select.dataset.enabledTitle = describe(select.value);
    else select.title = describe(select.value);
    showPrompt(select.value);
    fillPersonaMark($("persona-select-mark"), select.value);
  };
}

// You could choose a persona but never read what it told the model to do, 
// which makes the choice a guess. This shows the actual system prompt.
function togglePersonaPrompt() {
  const panel = $("persona-peek-panel");
  const showing = panel.classList.toggle("hidden");
  $("persona-peek").setAttribute("aria-expanded", !showing);
}

// A running total for the whole conversation. Per-message counts can't tell
// you when a thread has grown heavy enough to be worth starting over.
function renderChatUsage(tokens) {
  const el = $("chat-usage");
  if (!el) return;
  const total = Number(tokens) || 0;
  el.hidden = total === 0;
  el.textContent = total ? `${formatTokens(total)} tokens` : "";
  renderChatTurnCount();
}

//: **The conversation-level context meter.**
//:
//: Fed from the last turn's `stats` (prompt tokens against the window the turn
//: was budgeted for: `context_tokens`, which `ollama_client` has always sent).
//: Thresholds are Odysseus's: quiet under 70%, a warning at 70, a real alarm
//: at 85, because past about 85 the next turn starts losing the oldest part of
//: its own prompt and the answer quietly gets worse with nothing on screen
//: saying why.
function renderChatContextMeter(stats) {
  const pill = $("chat-context");
  if (!pill) return;
  const used = stats && Number(stats.prompt_tokens);
  const window = stats && Number(stats.context_tokens);
  if (!used || !window) {
    pill.hidden = true;
    return;
  }
  const pct = Math.min(100, Math.round((used / window) * 100));
  pill.hidden = false;
  // INBOX 77: "text wrong ... the badge shows 'used / window'". A raw
  // percentage answered "how full", which the colour already says at a
  // glance; the two counts answer the question a percentage cannot, how
  // much room is actually left to work with.
  pill.textContent = `${compactTokens(used)} / ${compactTokens(window)}`;
  pill.classList.toggle("is-warn", pct >= 70 && pct < 85);
  pill.classList.toggle("is-danger", pct >= 85);
  const approx = stats.usage_source === "estimated" ? "about " : "";
  pill.title = `The last turn used ${approx}${compactTokens(used)} of the model's ${compactTokens(window)} context window. Open for what fills it.`;
  //: The popover's rows (usage-ledger.js, lazy: the boot gzip ratchet).
  ensureModule("usageLedger").then(() => renderChatContextPop(stats, used, window, pct));
}


//: How long the thread is, beside what it has cost: Compress and Fork both answer "this has got long", which a token count does not say in a unit anyone thinks in.
function renderChatTurnCount() {
  const el = $("chat-turns");
  if (!el) return;
  const turns = (chatConv && chatConv.turns && chatConv.turns.length) || 0;
  el.hidden = turns === 0;
  el.textContent = turns === 1 ? "1 exchange" : `${turns} exchanges`;
}
