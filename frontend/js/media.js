// media.js: the sketch pad, image annotation, voice capture, meeting notes,
// read-aloud. Moved out of app.js on 2026-09-26 as one contiguous range (INBOX
// 426 cc, docs/roadmap/agent-remaining/appjs-split.md). A classic script
// sharing app.js's globals, loaded in app.js's old order; nothing in an earlier
// file calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- Wave F: whiteboard-lite --------------------------------------------------------

// **One highlighter, two renderers** (WHITEBOARD_PLAN decision 7, the half
// decided 2026-09-20). This pad paints into a `<canvas>` and the whiteboard
// paints SVG paths; two rendering models is a reason for two *painters*, not
// for two answers to "what is a highlighter". Every number here used to be
// two numbers: the board was 0.4 with a multiply blend and a 12 to 24 clamp,
// the pad 0.35 with no blend and no clamp, so one tool covered the paper on
// one surface and tinted it on the other (measured: one pass read 176.0 on a
// 255.0 paper here, which is the ink's own luminance, against 229.6 on a
// 252.9 board).
//
// It lives in app.js rather than whiteboard.js because whiteboard.js is
// lazily loaded (the module map near the foot of this file): whiteboard.js
// can read app.js, never the other way round.
const HIGHLIGHTER_STYLE = {
  // The plan's figure. Reported at 0.05 before Phase 3, where a stroke needed
  // roughly twenty overlapping passes to show at all and read as the tool
  // doing nothing.
  alpha: 0.4,
  // A nib, not a scaled pen: both width sliders reach 24 and four times that
  // is a wall, so the product is clamped to the range a real marker has.
  widthMultiplier: 4,
  minWidth: 12,
  maxWidth: 24,
  // A flat end is what a marker leaves; a round join is what keeps a
  // scribbled corner from reading as chipped.
  lineCap: "square",
  lineJoin: "round",
  // Multiply is worth 20 luminance units a pass over a light backdrop and 3
  // over a dark one (measured, WHITEBOARD_PLAN decision 7), so over a dark
  // one the highlighter screens instead: the same "two passes of one pen"
  // signal, in the direction that surface can actually move.
  blendOnLight: "multiply",
  blendOnDark: "screen",
};

// The one width both renderers ask for. Takes the pen width rather than
// reading one: the board's `WB_STROKE_WIDTH` is a `let` inside
// `initWhiteboard`, and a module-level function that read it threw on the
// first stroke.
function highlighterWidth(penWidth) {
  return Math.min(
    HIGHLIGHTER_STYLE.maxWidth,
    Math.max(HIGHLIGHTER_STYLE.minWidth, (penWidth || 3) * HIGHLIGHTER_STYLE.widthMultiplier),
  );
}


// --- Quick sketch: the app's half ---------------------------------------------------
//
// The pad itself is sketch-pad.js and sketch-pad.css, loaded on the first
// open: a self-contained paint pad (INBOX 1352) that asks the app for
// everything through the one host object below, so it can also run on a
// page of its own (tools/sketch-standalone/). What stays here is what
// only the app can do: save as a note, the toast and confirm dialogs, the
// stored preferences, the menu and help recipes and the highlighter's table.

let sketchHostObject = null;

function sketchHost() {
  sketchHostObject ||= {
    title: "Quick sketch",
    save: saveSketch,
    toast: (message, isError = false) => toast(message, isError),
    toastAction: (message, label, run) => toastAction(message, label, run),
    confirm: (message, options) => confirmDialog(message, options),
    prefs: {
      get: (key, fallback) => prefs.json(`sketch-pad-${key}`, fallback),
      set: (key, value) => prefs.setJSON(`sketch-pad-${key}`, value),
    },
    highlighter: HIGHLIGHTER_STYLE,
    menu: (items, label) => kebabMenu(items, label),
    wireHelp: (button, panel) => wireHelpPopover(button, panel),
    singleKeys: () => (typeof singleKeysOn === "function" ? singleKeysOn() : true),
    close: hideSketchOverlay,
  };
  return sketchHostObject;
}

//: `options.image` (a Blob) goes under the ink and `options.caption` into
//: the caption: the Annotate action on a picture (attachment-actions.js).
//: `options.host` stands in for the app's host: the capture card draws a
//: picture for the note it is writing (capture-card-more.js).
async function openSketch(options = {}) {
  overlayReturnFocus = document.activeElement;
  const loaded = await Promise.all([lazyScript("/css/sketch-pad.css"), lazyScript("/js/sketch-pad.js")]);
  if (!loaded.every(Boolean) || !window.SketchPad) {
    toast("Couldn't open the sketch pad.", true);
    return;
  }
  $("sketch-overlay").classList.remove("hidden");
  window.SketchPad.open($("sketch-card"), options.host || sketchHost(), options);
}

//: Asks the pad first: a drawing not yet saved is confirmed before it goes.
async function closeSketch() {
  if (window.SketchPad?.isOpen()) {
    await window.SketchPad.requestClose();
    return;
  }
  hideSketchOverlay();
}

function hideSketchOverlay() {
  $("sketch-overlay").classList.add("hidden");
  overlayReturnFocus?.focus?.();
  overlayReturnFocus = null;
}

//: The pad hands over the finished picture (paper, picture and ink as one
//: PNG) and the caption; a throw shows its message in the pad's status line.
async function saveSketch(blob, caption) {
  // **Through `/media/upload`, not `/entries/{id}/files`.** A sketch used
  // to be saved as an *attachment*, which is a different table and a
  // different pipeline: attachments are files hanging off a note, and only
  // `MediaUpload` rows are captioned, OCR'd, read by a vision model, or
  // listed in the Library's gallery. So a drawing was the one image in this
  // app that none of that ever touched, reported directly: "add captioning
  // and vision and ocr for sketches the user draws and saves as well".
  //
  // Uploading first and referencing the result in the note's markdown is
  // exactly what dropping an image into the note editor already does, so
  // this is now the same path rather than a second one: the picture appears
  // inline in the note, in the gallery, and in `media_process`'s queue.
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const form = new FormData();
  form.append("file", blob, `sketch-${stamp}.png`);
  const uploaded = await apiJson("/media/upload", {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  // The caption stays the note's own first line, it is what the person
  // typed and what the note is called. The image follows it.
  const entry = await apiJson("/entries", {
    method: "POST",
    body: JSON.stringify({
      content: `${caption}\n\n![${caption}](${uploaded.url})`,
      category: "Sketches",
    }),
  });
  if (!entry?.id) throw new Error("Couldn't save the sketch note.");
  pushEntryCreateUndo(entry, "Saved a sketch");
  toast("Sketch saved to your notebook.");
  loadEntries().catch(() => {});
}

// --- Wave H: voice capture (local Whisper) ------------------------------------------

let voiceStatus = null; // cached /voice/status
let recorder = null; // the active MediaRecorder, if any
let recorderTarget = null; // which input gets the transcript

// Live mic-level ring on a recording button, driven off the same MediaStream
// the recorder already opened, no extra permission, no extra stream.
// Returns a stop() that tears down the AudioContext; callers must invoke it
// before the stream's tracks are stopped.
// A small scrolling bar meter, Voice-Memos-style: five bars, oldest sample on
// the left, newest on the right, each redrawn from the analyser at ~15fps, 
// full 60fps would reshuffle the bars faster than a glance can read as a
// wave. The plain ring this replaced was a single number's worth of signal
// and, worse, was drawn in --warn-soft: a token pre-mixed pale enough that on
// a near-white modal card it was measured, by screenshot, as functionally
// invisible: that's what "no animation" on the meeting recorder turned out
// to be. --recording-ring (a solid --warn mixed at capture time, defined
// alongside button.recording below) replaced it there and is reused here.
const MIC_BAR_COUNT = 5;
const MIC_BAR_SAMPLE_EVERY = 4; // frames between bar updates, ~15fps at 60fps rAF
// getByteFrequencyData's 128 bins (at fftSize=256) span the full 0-22kHz
// range, but speech energy sits almost entirely under ~5.5kHz. Averaging
// every bin, the previous behaviour, mixed a real voice signal with ~100
// near-silent high-frequency bins and diluted it to a fraction of what a
// human ear perceives as "there's sound". Restricting the average to the
// low bins reflects what's actually in a voice.
const MIC_BAR_SPEECH_BIN_FRACTION = 0.25;
// Reported live as "the bars don't show even at minimum sound pick-up":
// at a 0.12 floor, a 14px bar renders under 2px tall, not subtle, just
// below what's visible. 0.12 was chosen to read as "listening, not
// frozen" (see below) but never accounted for how few pixels that scale
// actually leaves. Raised so the resting state itself is visible.
const MIC_BAR_MIN_SCALE = 0.3;

//: **The microphone as chosen** (UI_MODERNISATION V2, INBOX 828: "noise
//: supression, voice enhancement, audio input devices ... need to be
//: managable"): the device and the browser's own three cleanups, kept on
//: this computer, asked for by every recorder (dictation, a voice note, a
//: meeting, live captions). `ideal`, not `exact`: a microphone unplugged
//: since falls back to the default rather than refusing to record.
function micAudioConstraints() {
  const device = prefs.get("micDevice", "");
  return {
    ...(device ? { deviceId: { ideal: device } } : {}),
    noiseSuppression: prefs.bool("micNoise", true),
    echoCancellation: prefs.bool("micEcho", true),
    autoGainControl: prefs.bool("micGain", true),
  };
}

function startMicLevelMeter(stream, button) {
  let ctx;
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
  } catch {
    return () => {}; // no Web Audio support, recording still works, just no meter
  }
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);
  const data = new Uint8Array(analyser.frequencyBinCount);
  const speechBinCount = Math.round(data.length * MIC_BAR_SPEECH_BIN_FRACTION);
  button.classList.add("live-level");

  const bars = document.createElement("span");
  bars.className = "mic-bars";
  bars.setAttribute("aria-hidden", "true");
  const barEls = Array.from({ length: MIC_BAR_COUNT }, () => {
    const bar = document.createElement("span");
    bar.className = "mic-bar";
    bars.appendChild(bar);
    return bar;
  });
  button.appendChild(bars);
  const history = new Array(MIC_BAR_COUNT).fill(0);

  let tickCount = 0;
  let frame = null;
  let stopped = false;

  function startLoop() {
    if (stopped) return;
    frame = requestAnimationFrame(function tick() {
      if (stopped) return;
      analyser.getByteFrequencyData(data);
      let sum = 0;
      for (let i = 0; i < speechBinCount; i++) sum += data[i];
      const avg = sum / speechBinCount;
      if (tickCount % MIC_BAR_SAMPLE_EVERY === 0) {
        // sqrt, not linear: ordinary speaking volume sits low in the raw
        // 0-255 range, and a linear map leaves it barely above the resting
        // floor. The square root curve lifts quiet-to-moderate signal
        // (where a voice actually lives) without letting loud input clip.
        history.push(Math.sqrt(avg / 255));
        history.shift();
        history.forEach((level, i) => {
          // A silent bar never fully flattens, Voice Memos' own resting bars
          // read as "listening", a flat line reads as "frozen".
          barEls[i].style.setProperty("--bar-scale", Math.max(level, MIC_BAR_MIN_SCALE).toFixed(3));
        });
      }
      tickCount++;
      frame = requestAnimationFrame(tick);
    });
  }

  // Some browsers (including Chrome on Windows) create AudioContext suspended
  // even inside a click handler. The analyser returns all-zero until the
  // context is actually running. Wait for resume() to resolve rather than
  // firing the loop immediately and reading silence on the first N frames.
  // A small additional delay lets the OS audio stack fully open the device.
  ctx.resume().then(() => {
    setTimeout(startLoop, 150);
  }).catch(() => {
    // resume() failed: start anyway; if it's really suspended the bars just
    // stay at their floor scale, which is still visible and shows the button
    // is in recording state.
    setTimeout(startLoop, 150);
  });

  return () => {
    stopped = true;
    if (frame !== null) cancelAnimationFrame(frame);
    button.classList.remove("live-level");
    bars.remove();
    source.disconnect();
    ctx.close().catch(() => {});
  };
}

async function toggleDictation(button, targetInput) {
  if (recorder) {
    recorder.stop(); // second press = stop → transcribe
    return;
  }
  if (voiceStatus === null) {
    voiceStatus = await apiJson("/voice/status").catch(() => ({ available: false }));
  }
  if (!voiceStatus.available) {
    toast(voiceStatus.hint || "Voice capture isn't available.");
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraints() });
  } catch {
    toast("Microphone access was blocked, allow it in your browser.", "info");
    return;
  }
  //: **The button's resting label, read once and kept.** Reported: the word
  //: "Dictate" disappears the first time you record and never comes back.
  //: `setLabel` replaces every child of the button, so the two calls below
  //: were swapping the glyph and dropping the word with it; the stop handler
  //: then restored a bare microphone, which is the state the report describes.
  //:
  //: Read here rather than inside the stop handler because by then the only
  //: label on the button is "Stop", and kept on the element rather than in a
  //: closure because a second recording starts a new one. The chat mic
  //: (`#mic-chat`) is `icon-only` and has no `.ph-text` at all: it reads as an
  //: empty string and must stay that way, or it gains a word and stops being
  //: square.
  if (button.dataset.restLabel === undefined) {
    button.dataset.restLabel = button.querySelector(".ph-text")?.textContent?.trim() || "";
  }
  const resting = button.dataset.restLabel;
  const chunks = [];
  recorder = new MediaRecorder(stream);
  recorderTarget = targetInput;
  let stopLevelMeter = () => {};
  recorder.addEventListener("dataavailable", (e) => chunks.push(e.data));
  recorder.addEventListener("stop", async () => {
    stream.getTracks().forEach((t) => t.stop());
    stopLevelMeter();
    button.classList.remove("recording");
    setLabel(button, resting ? `ph:microphone ${resting}` : "ph:microphone");
    recorder = null;
    const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
    const form = new FormData();
    form.append("file", blob, "clip.webm");
    toast("Transcribing…");
    try {
      // `api.upload` (F5); a refusal throws the server's sentence.
      const body = await (await api.upload("/voice/transcribe", form)).json();
      const box = recorderTarget;
      box.value = box.value ? `${box.value.trimEnd()} ${body.text}` : body.text;
      box.focus();
    } catch (error) {
      toast(error.message, true);
    }
  });
  recorder.start();
  button.classList.add("recording");
  setLabel(button, resting ? "ph:stop Stop" : "ph:stop");
  // Appended after setLabel, not before: setLabel's replaceChildren() wipes
  // every child on the button, and the bar meter startMicLevelMeter() builds
  // is one: appending it earlier just got it discarded a line later.
  stopLevelMeter = startMicLevelMeter(stream, button);
}

// --- Wave H: read-aloud (the browser's local voices) --------------------------------

//: `button` shows a stop icon and `aria-pressed` while it speaks (INBOX 1423).
function speakText(text, button = null) {
  if (!("speechSynthesis" in window)) {
    toast("This browser has no text-to-speech voices.", "info");
    return;
  }
  if (speechSynthesis.speaking) {
    speechSynthesis.cancel(); // acting as a stop button
    return;
  }
  if (!text.trim()) return;
  const utterance = new SpeechSynthesisUtterance(text);
  if (button) {
    const rest = button.innerHTML;
    const paint = (on) => {
      button.setAttribute("aria-pressed", String(on));
      if (on) setLabel(button, "ph:stop");
      else button.innerHTML = rest;
    };
    utterance.addEventListener("start", () => paint(true));
    for (const type of ["end", "error"]) utterance.addEventListener(type, () => paint(false));
  }
  //: Read aloud is sound this app makes, so the companion can hear it.
  if (typeof nameMarkBuddySound === "function") {
    utterance.addEventListener("start", () => nameMarkBuddySound("speech", true));
    for (const type of ["end", "error"]) utterance.addEventListener(type, () => nameMarkBuddySound("speech", false));
  }
  speechSynthesis.speak(utterance);
}
