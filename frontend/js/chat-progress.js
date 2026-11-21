// chat-progress.js: battery mode, motion, the writing trace, wheel scroll, thinking words and progress phases. A classic script sharing the page globals, split out of chat.js (L-world-class-770); loaded right after it.

// Three-dot "the model is about to speak" indicator (Wave D).
// "The model is working." Under reduced motion the bouncing dots are frozen by
// the blanket animation rules, three motionless dots say nothing at all, and
// read as a rendering fault rather than as progress. So when motion is off,
// this becomes a word instead of a gesture. Silence is not an acceptable
// substitute for either.
//: **Battery-efficient mode, as the two generative pictures see it**
//: (INBOX 260). The setting pauses the background AI tasks and the graph's
//: similarity work, and for a long time reached nothing in the browser: a
//: person who turned on a setting with "battery" in its name and watched
//: the dashboard's constellation keep drawing would reasonably call that
//: broken, whatever the help text said. So it is a third input to the motion
//: resolution `startArt` (dashboard.js) and `startBgArt` (settings.js)
//: already share with reduced motion and Performance mode, and the help text
//: says so now.
//:
//: Here rather than beside the other two because app.js is the first script
//: the page loads and `prefsCache` is its own; the `typeof` guard is the
//: same one every cross-file reading in this app carries, since a picture
//: can start before the preferences have landed.
function batteryModeOn() {
  return Boolean(prefsCache && prefsCache.battery_efficient_mode);
}

// `label` is the reduced-motion fallback: with animations off the dots can't
// convey "working", so a word has to. Callers that already print their own
// sentence beside the indicator pass theirs in, the weekly digest used to
// append " Thinking about your week…" next to the default, and it rendered as
// "Thinking… Thinking about your week…" (user-reported).
//: **Progress is feedback, not decoration, and it gets its own switch.**
//:
//: Reported three times, the last with a screenshot of a frozen italic
//: "Thinking…": *"the thinking and writing animation is completely broken,
//: doesn't move"*, and then the instruction that settles the design, 
//: *"make them happen even if animations are stalled, or make them paused
//: separately to the rest like the background art."*
//:
//: The background art already has exactly that shape (`bg-motion`: auto /
//: moving / still), so this follows it rather than inventing a second idea.
//: The difference is the **default**: the art defaults to `auto` because it
//: is decoration, and this defaults to `always` because a progress indicator
//: that has stopped is indistinguishable from an app that has hung. Turning
//: off "animations and transitions" is a statement about chrome; it was
//: never a request to be left unable to tell whether the model is working.
//:
//: The OS's own `prefers-reduced-motion` is still honoured under `auto`, and
//: `alive()` below is what stops that meaning *dead*, see its own comment.
function progressMotionWanted() {
  const choice = document.documentElement.dataset.progressMotion || "always";
  if (choice === "still") return false;
  //: **"Always" means always, including through the platform setting**, by
  //: direct instruction: *"make sure the animations run even with prefer
  //: reduced motion on, like the rotating generated logos."* My first pass
  //: exempted the OS setting on accessibility grounds and was overruled, it
  //: is the user's own app, the choice is theirs, and it is one select away
  //: from `auto`, which does respect the platform. The CSS counter-rule in
  //: 02-chat-graph.css carries the same decision for the same reason.
  if (choice === "always") return true;
  return !reducedMotionWanted();
}

// `label` is the reduced-motion fallback: with animations off the dots can't
// convey "working", so a word has to. Callers that already print their own
// sentence beside the indicator pass theirs in, the weekly digest used to
// append " Thinking about your week…" next to the default, and it rendered as
// "Thinking… Thinking about your week…" (user-reported).
//: The writing motif: three nodes and the edge being drawn between them, 
//: the same node-and-edge vocabulary the graph, the concept maps and the app's
//: own mark are built from. Inline SVG with attributes rather than a `style`
//: string, because this app's CSP drops inline styles (CLAUDE.md, "a policy
//: silently refusing the work"); everything that moves is done in CSS.
//: **An interval that belongs to a node, and survives that node being moved.**
//:
//: The pattern this replaces was `if (!node.isConnected) return
//: clearInterval(timer)`, correct about the leak it was guarding (an interval
//: that outlives its element grows with every turn of a long conversation) and
//: wrong about what "gone" means. **A node that is being re-parented is
//: disconnected for an instant**, and this app re-parents the streaming
//: indicator on purpose: `reattachStreamingTurn` appends every node of the
//: live turn back into `#chat-messages` whenever the pane is rebuilt, and
//: `clearPending` moves the pending line to the end of the steps.
//:
//: One tick landing inside one of those windows killed the timer for good.
//: The node came back, the animation did not, and it froze mid-cycle showing
//: its three dots standing still, reported as "the text streaming animation
//: stops moving and just shows as 3 lines", and again as "I scrolled up while
//: still streaming the response and the generating and animation disappeared",
//: which is the same timer dying during the re-render that scrolling caused.
//:
//: So: skip the work while detached, and only give up once the node has stayed
//: gone for `GRACE_TICKS` in a row. A re-parent is one frame; ten ticks is
//: several seconds, which is far longer than any re-render and still bounded,
//: so the leak the original guard was written for cannot come back.
const LIVING_INTERVAL_GRACE_TICKS = 10;

function aiWritingTrace() {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "ai-writing-trace");
  svg.setAttribute("viewBox", "0 0 34 12");
  svg.setAttribute("aria-hidden", "true"); // the container already announces itself
  const line = document.createElementNS(NS, "path");
  line.setAttribute("class", "ai-writing-edge");
  line.setAttribute("d", "M4 8 L17 4 L30 8");
  svg.append(line);
  const nodes = [
    [4, 8],
    [17, 4],
    [30, 8],
  ];
  nodes.forEach(([cx, cy], index) => {
    const dot = document.createElementNS(NS, "circle");
    dot.setAttribute("class", `ai-writing-node ai-writing-node-${index + 1}`);
    dot.setAttribute("cx", cx);
    dot.setAttribute("cy", cy);
    dot.setAttribute("r", "2");
    svg.append(dot);
  });
  return svg;
}

//: **Two phases**: `thinking` keeps the dots, `writing` draws a short run of
//: nodes joined by a line (this app's motif). Both sit stacked in one box and
//: cross-fade, so the swap never shifts layout; the SVG goes after the dot
//: spans because `:nth-child(2)`/`(3)` time the bounce by position.
//: **A mouse wheel must scroll a horizontal strip.** Reported: "if the tabs
//: bar becomes scrollable, I cant do it with mouse, only with touch or my
//: trackpad."
//:
//: That is the browser's behaviour, not a bug in the strip: a wheel emits
//: `deltaY`, and an element that only overflows on X ignores it, so a
//: trackpad (which emits real `deltaX` on a two-finger swipe) and a
//: touchscreen work while a wheel does nothing at all. Every app with a tab
//: strip translates the axis by hand; this is that, once, for all of them.
//:
//: Three conditions before it takes over, so it never steals a gesture that
//: meant something else: the element must actually overflow horizontally, the
//: gesture must be vertical-only (`deltaX === 0`, a trackpad's own horizontal
//: swipe is left alone), and the scroll must have somewhere to go in that
//: direction, so at either end the page scrolls normally instead of the strip
//: swallowing the wheel.
//:
//: `passive: false` because it calls `preventDefault`; that is the whole
//: point, and it is scoped to elements that pass the test above.
function wheelScrollsHorizontally(element) {
  if (!element || element.dataset.wheelX === "1") return;
  element.dataset.wheelX = "1";
  element.addEventListener(
    "wheel",
    (event) => {
      if (event.deltaX !== 0 || event.shiftKey) return;
      // Do not steal vertical scroll if the target is inside a scrollable dropdown/menu
      if (event.target.closest(".select-menu, .action-menu, .doc-dock-menu-list, .library-image-menu-list, .wb-board-menu")) return;
      
      const room = element.scrollWidth - element.clientWidth;
      if (room <= 1) return;
      const atStart = element.scrollLeft <= 0 && event.deltaY < 0;
      const atEnd = element.scrollLeft >= room - 1 && event.deltaY > 0;
      if (atStart || atEnd) return;
      element.scrollLeft += event.deltaY;
      event.preventDefault();
    },
    { passive: false }
  );
}
window.wheelScrollsHorizontally = wheelScrollsHorizontally;

// Trackpads send small deltaX values along with deltaY when scrolling vertically.
// If a dropdown lacks horizontal scroll, browsers often ignore `overscroll-behavior` 
// on that axis and chain the deltaX to the nearest horizontally scrollable ancestor.
// When the ancestor scrolls, `closeActionMenusOnScroll` fires and closes the menu.
// [REMOVED] The manual wheel event handler was removed because `menu.scrollTop += event.deltaY`
// breaks two-finger trackpad scrolling. Instead, `closeActionMenusOnScroll` now checks 
// if the cursor is actively hovering the menu, and if so, it ignores the ancestor scroll event.

//: Every horizontal strip in the app, in one list. A strip added later gets
//: this by being added here, which is cheaper than each surface remembering.
function wireHorizontalWheelScrolling() {
  const strips = [
    "#tab-bar",
    "#notes-subtabs",
    "#library-subtabs",
    ".doc-toolbar",
    ".seg.edge-fade",
    ".edge-fade",
  ];
  for (const selector of strips) {
    for (const element of document.querySelectorAll(selector)) {
      wheelScrollsHorizontally(element);
    }
  }
}
window.wireHorizontalWheelScrolling = wireHorizontalWheelScrolling;

//: **Recursive, not `livingInterval`.** That helper (this file, above) fixes
//: one period for the whole life of the timer; a jittered 3.75-to-5.25s gap
//: needs a new random delay every tick, so this reimplements its one other
//: idea by hand: a node re-parented for a frame (this app re-parents a live
//: turn's own elements on purpose, see `livingInterval`'s comment) is not a
//: node that is gone, so a handful of short rechecks are given before the
//: timer actually stops, rather than the leak the naive
//: `if (!node.isConnected) return` guard used to be.
//: 1.5x the first 2.5-to-3.5s gap: the owner found that pace a little too
//: fast to read a phrase before it changed (2026-09-28).
const THINKING_WORD_MIN_MS = 3750;
const THINKING_WORD_JITTER_MS = 1500;
const THINKING_WORD_RECHECK_MS = 500;
const THINKING_WORD_GRACE_TICKS = 4;

function scheduleThinkingWordTick(dots, wordEl, list, index, missingTicks) {
  dots._thinkingWordTimer = setTimeout(() => {
    //: **Stop on phase "writing"**, checked here rather than only in
    //: `setPhase`, so the one tick already in flight when the phase flips
    //: mid-wait cannot still land a rotation moments after the answer has
    //: started.
    if (dots.dataset.phase === "writing") return;
    if (!dots.isConnected) {
      if (missingTicks + 1 >= THINKING_WORD_GRACE_TICKS) return; // gone for good
      scheduleThinkingWordTick(dots, wordEl, list, index, missingTicks + 1);
      return;
    }
    const next = (index + 1) % list.length;
    //: The exact crossfade `.progress-musing` uses (this file, `progressLine`):
    //: remove the class, force a reflow, add it back, so the transition
    //: restarts on an element already on screen rather than coalescing into
    //: nothing.
    wordEl.classList.remove("is-shown");
    void wordEl.offsetWidth;
    wordEl.textContent = list[next];
    wordEl.classList.add("is-shown");
    scheduleThinkingWordTick(dots, wordEl, list, next, 0);
  }, missingTicks > 0 ? THINKING_WORD_RECHECK_MS : THINKING_WORD_MIN_MS + Math.random() * THINKING_WORD_JITTER_MS);
}

//: Only for the enhanced-motion indicator (dots + the writing trace): under
//: reduced motion `typingDots` never reaches this, and its own single word
//: already satisfies "show one word, no rotation" without help.
function startThinkingWordRotation(dots, persona) {
  const list = thinkingWordsFor(persona);
  const wordEl = document.createElement("span");
  wordEl.className = "typing-thinking-word";
  //: **Not announced per word.** The row's own `aria-label` (set once, by
  //: the caller) is what a screen reader reads, "Thinking"; a value that
  //: changes several times a minute read aloud each time would be noise, not
  //: help, so the word is decorative.
  wordEl.setAttribute("aria-hidden", "true");
  //: No reserved width: sized to the longest phrase it pushed "Thinking" and
  //: the tips far to the right (the owner at release, twice). The word sits
  //: last in its row, so a shorter or longer phrase moves nothing after it.
  wordEl.textContent = list[0];
  dots.appendChild(wordEl);
  //: The first word arrives the same way every later one does (a frame after
  //: attach, so the transition has something to animate from) rather than
  //: starting already shown, which is one fewer rule for this word to answer
  //: to differently from every other rotation it does.
  requestAnimationFrame(() => wordEl.classList.add("is-shown"));
  scheduleThinkingWordTick(dots, wordEl, list, 0, 0);
}

function stopThinkingWordRotation(dots) {
  clearTimeout(dots._thinkingWordTimer);
  dots._thinkingWordTimer = null;
}

//: **One phase vocabulary for every chat surface** (INBOX 649, the owner: the
//: "thinking..." text "should change based on the state like for if it is
//: waiting for the first token, thinking, or writing etc. maybe the wording
//: can be more atlas themed ... just to help with information architecture").
//: Decided, not to be remade: waiting for the first token "Reaching Atlas…",
//: a model loading "Waking the model…", retrieval "Reading your notes…",
//: reasoning tokens "Atlas is thinking…", answer text "Atlas is writing…", a
//: tool call "Atlas is <tool verb>…". With no model connected, "Working it
//: out without a model…" (INBOX 801). A persona's name replaces Atlas. The
//: indicator keeps its own two shapes (dots, or the writing trace under
//: "writing", which CSS keys off `data-phase`); only the words have six
//: states. Every surface
//: drives it through `progressLine(...).setPhase(name, detail)`, and the shared
//: stream client (`streamChat`, capture-ask.js) does so from the events that
//: really arrive, so no surface invents a stage.
const PROGRESS_PHASES = {
  reaching: (who) => `Reaching ${who}…`,
  loading: () => "Waking the model…",
  //: With no model connected (INBOX 801, the owner: "It said waking a model
  //: when no model is connected"): the app's own engine is answering.
  engine: () => "Working it out without a model…",
  reading: () => "Reading your notes…",
  thinking: (who) => `${who} is thinking…`,
  writing: (who) => `${who} is writing…`,
  tool: (who, verb) => `${who} is ${verb || "using a tool"}…`,
};

function progressPhaseText(phase, persona = null, detail = null) {
  if (!PROGRESS_PHASES[phase]) return null;
  return PROGRESS_PHASES[phase](personaDisplayName(persona), detail);
}

//: **A tool's own label, as the verb of the sentence.** The harness labels a
//: call in the past tense once it has run (`ph:books Listed notes`, `Searched
//: notes for “x”`), the only label there is; its first word becomes the
//: present participle ("listing notes", "searching notes for “x”"). Regular
//: past tenses lose their `ed` and gain `ing` (`Saved` to `saving`, `Tagged` to
//: `tagging`), the few irregulars the harness uses are listed, and a label that does not
//: open with a verb ("No path between #1 and #2") gives null, which the phase
//: renders as "using a tool".
const TOOL_VERB_IRREGULAR = { read: "reading", found: "finding", put: "putting", got: "getting", took: "taking", drew: "drawing" };

//: `words`: opt in, not automatic. Most callers (an OCR read, a caption, a
//: generic "Loading…") are not "the AI is thinking about your question",
//: and a persona's voice rotating beside them would be decoration with
//: nothing behind it. `persona`: whoever is answering, resolved once by the
//: caller (the same value the request itself was sent with, `chat-attach.js`'s
//: own `sentPersona`, `palette.js`'s `askedPersona`), never read back off a
//: live picker here.
function typingDots(label = null, { persona = null, words = false } = {}) {
  label = label || progressPhaseText("reaching", persona);
  const dots = document.createElement("span");
  //: `typing-dots` is kept as the class even though this is now two
  //: indicators: existing CSS keys off it, and so does the code that removes
  //: the indicator when the first token lands
  //: (`querySelector(".typing-dots, .typing-label")`). Renaming it would have
  //: been a silent breakage in surfaces this change never meant to touch.
  dots.className = "typing-dots";
  dots.dataset.phase = "thinking";
  dots.setAttribute("role", "status");
  dots.setAttribute("aria-label", label);
  dots.setStatus = (next) => {
    dots.setAttribute("aria-label", next);
  };
  if (progressMotionWanted()) {
    //: `.typing-dot`, not a bare `<span>`: the thinking word appended below
    //: is a *fourth* span in this row, and `.typing-dots span` (01-forms
    //: -settings.css) matched it too, leaking a dot's circle, fill and
    //: bounce onto it (the owner's "a long line... an annoying pulse").
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement("span");
      dot.className = "typing-dot";
      dots.appendChild(dot);
    }
    dots.appendChild(aiWritingTrace());
    //: Idempotent, because the streaming callbacks that drive this fire on
    //: every delta: setting the same phase again must not restart the
    //: cross-fade or the line would stutter on each token.
    dots.setPhase = (phase) => {
      const next = phase === "writing" ? "writing" : "thinking";
      dots.dataset.phaseName = phase;
      if (dots.dataset.phase !== next) {
        dots.dataset.phase = next;
        if (next === "writing") stopThinkingWordRotation(dots);
      }
    };
    if (words && wantsThinkingWords()) {
      startThinkingWordRotation(dots, persona);
    }
    return dots;
  }

  //: **INBOX 36: stepping a dot's colour once a second did not read as
  //: alive.** The previous fix here (a class moving from dot to dot) was
  //: reasoned, not observed, and the owner's desktop shell still showed a
  //: flat row of dots: `.typing-dots-stepped span.is-on` swapped `--border`
  //: for `--accent`, a colour change with no size, position or brightness
  //: cue big enough to notice out of the corner of an eye while reading an
  //: answer. Reported again, unchanged: "the streaming indicator still does
  //: not animate."
  //:
  //: A word that changes is unambiguous in a way three near-identical dots
  //: never were, and a *slow* opacity pulse is movement of the one kind
  //: `prefers-reduced-motion` guidance treats as safe: no translation, no
  //: scaling, nothing that can trigger vestibular symptoms, just a fade
  //: between two brightness levels over several seconds. The word itself
  //: still changes with the phase, the same "value changing is information"
  //: reasoning the old stepped dots were built on, just legible this time.
  dots.classList.add("typing-dots-stepped");
  const word = document.createElement("span");
  word.className = "typing-word";
  //: The caller's own words first (`label` is this branch's whole voice), then
  //: the phase vocabulary's, so a standalone indicator under reduced motion
  //: says "Atlas is writing…" rather than one of two bare words.
  word.textContent = label;
  dots.appendChild(word);
  dots.setPhase = (phase, detail) => {
    const next = phase === "writing" ? "writing" : "thinking";
    dots.dataset.phaseName = phase;
    dots.dataset.phase = next;
    const text = progressPhaseText(phase, persona, detail);
    if (text && word.textContent !== text) word.textContent = text;
  };
  return dots;
}

// **A working signal that says what it is working on.** Under reduced
// motion the dots become one static word, so the label the stream updates
// (what it is doing now, from events that actually happened, never a guessed
// stage) is what keeps a long turn from reading as dead.
//: Lines shown while you wait are fixed facts about this app, not model
//: whimsy: a fixed list cannot hallucinate a privacy claim.
const PROGRESS_MUSINGS = [
  "Everything here runs on your machine, nothing is sent anywhere.",
  "Your notes are plain markdown on disk. You can read them without this app.",
  "Searching uses meaning and keywords together, then merges the two rankings.",
  "A note you never tagged is still findable, the links between notes count too.",
  "Private notes are held back from Atlas, even when it asks for them.",
  "Ask mode reads. Agent mode asks before changing a note.",
  "Long answers are slower on a small model, not stuck.",
  "Every tool call Atlas makes is listed under the answer, with what it touched.",
  "Type [[ in any note to link to another one.",
  "Select text anywhere you can edit and ask Atlas about just that passage.",
];

//: How long to wait before showing one. A turn that finishes in a second
//: should never flash a sentence nobody had time to read.
const MUSING_DELAY_MS = 2500;
//: And how long each stays. Long enough to read twice, short enough that a
//: minute-long wait is not one sentence.
const MUSING_ROTATE_MS = 7000;

// Coalesce scroll-to-end into one write per animation frame. It used to run
// on every streamed token, forcing a synchronous reflow each time, a big
// source of jank on long answers.
let chatScrollQueued = false;
