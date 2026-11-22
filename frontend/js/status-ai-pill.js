// status-ai-pill.js: the AI status dot's reading and its paint (`aiStatusState`, `aiOffGlyph`, `lastAnswerLine`,
// `renderAiPill`). Moved out of status.js (LEDGER L-world-class-810) to come off the boot file: lazy, the
// `statusAiPill` bundle with a stand-in for `renderAiPill` in lazy-entries.js, its only door. Nobody reads a
// return value (the status poll and the chat's turn end call it); the state it reads (`modelStatus`,
// `statusEverAnswered`, `lastAnswerFacts`) stays in status.js, which the chat writes to.

// What the AI is doing, as one decision.
//
// Three levels, and the boundary between them is deliberate. This app is built
// to degrade gracefully, so "no AI at all" is a supported way to run it, not a
// fault: it is amber, not red. Red is reserved for something that is actually
// broken: a model that failed to load, or a server we can't reach. Colouring a
// normal offline setup red would train the user to ignore the indicator.
//
//   idle  … grey    haven't heard back yet, says nothing either way
//   ok    ✓ green   everything the AI can do is available
//   off   AI sparkle, slashed, grey: no model connected, the offline way to run
//   warn  ! amber   loading or rebuilding, app works
//   error ✕ red     something is broken and won't fix itself
function aiStatusState() {
  if (!modelStatus) {
    // The first poll of every page load lands here for a moment. Reporting
    // that as a fault would flash red on every startup and teach the user
    // that red means nothing, so an unanswered *first* request is its own
    // quiet state, and only a request that has failed after we have already
    // had an answer counts as the server going away.
    if (!statusEverAnswered) {
      return {
        level: "idle",
        title: "Checking…",
        detail: "Asking the app what Atlas is doing. This takes a moment.",
      };
    }
    return {
      level: "error",
      title: "Can't reach Tessellate",
      detail:
        "The app can't read its own status, which usually means the server " +
        "stopped. Your notes are safe on disk.",
    };
  }
  const chatReady = modelStatus.ollama_running;
  const searchReady = modelStatus.embedding_ready;

  if (modelStatus.reindex && modelStatus.reindex.status === "running") {
    return {
      level: "warn",
      title: "Rebuilding the search index",
      detail:
        "Searching by word works while this runs. Searching by meaning comes " +
        "back when it finishes.",
    };
  }
  if (!searchReady && modelStatus.embedding_warming) {
    return {
      level: "warn",
      title: "Search AI is warming up",
      detail:
        "Searching by word works now. Searching by meaning becomes available " +
        "once the model has loaded.",
    };
  }
  if (!searchReady && modelStatus.embedding_error) {
    // "Broken" and "still loading" looked identical before: the old pill said
    // "warming up…" forever when the model had actually failed. Never
    // allowed to download (yet) is a choice, not a fault (audit 1030 Y2).
    const off = modelStatus.semantic_off;
    return {
      level: off ? "off" : "error",
      title: off ? "Search by meaning off" : "Search AI didn't load",
      detail:
        `${modelStatus.embedding_error}\n\nSearching by word still works, and ` +
        "notes, tags, reminders and the graph are unaffected." + (off ? "" : " Settings, Logs has the details."),
    };
  }
  if (chatReady && searchReady) {
    return {
      level: "ok",
      title: "AI ready",
      detail: "Chat, auto-filing and search by meaning are all available.",
    };
  }
  // Everything below leads with what still WORKS. Announcing a fault and
  // pointing at a log reads as "the app is broken" when in fact only the
  // optional half is missing.
  //: **"off", not "warn"** (INBOX 472, the first-run walk): this is the
  //: supported way to run, and an amber "!" (a 44px amber circle in the
  //: phone's top bar) was the loudest thing on a new person's first screen.
  //: Neutral, with the ring Settings, Models draws beside "isn't running".
  if (!chatReady && searchReady) {
    return {
      level: "off",
      title: "Notebook ready · chat AI off",
      detail:
        "Notes, search, tags, reminders and the graph all work. Connect a " +
        "model in Settings, Models to add chat and auto-filing.",
    };
  }
  if (chatReady && !searchReady) {
    return {
      level: "warn",
      title: "Word search on · AI search warming",
      detail:
        "Searching by word works now; searching by meaning becomes available " +
        "once the embedding model has loaded.",
    };
  }
  return {
    level: "off",
    title: "Notebook ready · AI off",
    detail:
      "Writing, searching, tagging, reminders, documents and the graph all " +
      "work without any AI. Connect a model in Settings, Models to add chat, " +
      "auto-filing and search by meaning.",
  };
}

// The glyph is not decoration. Colour alone fails for the ~8% of men with a
// colour vision deficiency, and fails everyone in high-contrast mode, so the
// shape carries the same meaning the colour does.
// "…" for connecting rather than a spinner: a spinner has to be animated to
// read as one, and under reduced motion a frozen spinner looks like a
// rendering fault. The ellipsis says "waiting" while perfectly still.
const AI_STATUS_GLYPH = { idle: "…", ok: "✓", warn: "!", error: "✕", off: "" };

//: **"AI off" is the app's AI sparkle with a slash** (INBOX 656, the owner:
//: "can the no ai available ai status icon be better??"). It was a hollow
//: ring, which said nothing; the sparkle is what every AI control here wears
//: (Ask, Refine, the agent), and the slash, cut clear of it by a mask so it
//: reads at 14px, says it is not connected. It stays in the muted ink on the
//: chip, never amber: the notebook is fine, which is the card's first words.
//: An svg in `currentColor`, not the icon font plus a pseudo-element, so it
//: costs the boot stylesheet nothing and centres by the dot's own grid.
function aiOffGlyph() {
  const ns = "http://www.w3.org/2000/svg";
  const make = (tag, attrs, parent) => {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (parent) parent.appendChild(el);
    return el;
  };
  const svg = make("svg", { class: "ai-off-glyph", viewBox: "0 0 16 16", width: "14", height: "14", fill: "none", stroke: "currentColor", "stroke-width": "1.5", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" });
  const mask = make("mask", { id: "ai-off-gap", maskUnits: "userSpaceOnUse", x: "0", y: "0", width: "16", height: "16" }, make("defs", {}, svg));
  make("rect", { width: "16", height: "16", fill: "white", stroke: "none" }, mask);
  make("path", { d: "M2.5 2.5L13.5 13.5", stroke: "black", "stroke-width": "3.4" }, mask);
  make("path", { d: "M8 1.4Q9.9 6.1 14.6 8Q9.9 9.9 8 14.6Q6.1 9.9 1.4 8Q6.1 6.1 8 1.4Z", mask: "url(#ai-off-gap)" }, svg);
  make("path", { d: "M2.5 2.5L13.5 13.5" }, svg);
  return svg;
}

function lastAnswerLine() {
  const facts = lastAnswerFacts;
  if (!facts || !facts.ms) return "";
  const parts = [facts.model, `${(facts.ms / 1000).toFixed(1)} s`];
  if (facts.used && facts.window) parts.push(`${Math.min(100, Math.round((facts.used / facts.window) * 100))}% of its window`);
  return `Last answer: ${parts.filter(Boolean).join(", ")}.`;
}

function renderAiPill() {
  const button = $("ai-status");
  if (!button) return;
  const state = aiStatusState();
  button.dataset.level = state.level;
  //: "Checking" is three dots drawn by CSS, not "…": an ellipsis sits on the
  //: baseline in every font and the icon font's dots sit above the middle,
  //: 3px off either way (INBOX 435, measured); a box of known size is
  //: centred by the dot's own grid. ✓, ! and ✕ are within half a pixel.
  const dot = button.querySelector(".ai-status-dot");
  if (state.level === "off") {
    if (!dot.querySelector(".ai-off-glyph")) dot.replaceChildren(aiOffGlyph());
  } else dot.textContent = state.level === "idle" ? "" : AI_STATUS_GLYPH[state.level];
  // The button's own name for screen readers and for the native tooltip, so
  // the information is reachable without opening anything.
  const summary = `AI status: ${state.title}`;
  $("ai-status-label").textContent = summary;
  // button.title = `${state.title}\n\n${state.detail}`;
  $("ai-status-title").textContent = state.title;
  const last = lastAnswerLine();
  $("ai-status-detail").textContent = last ? `${state.detail} ${last}` : state.detail;
  renderChatActiveModelBadge();
  nudgeEmbeddingProblem();
}
