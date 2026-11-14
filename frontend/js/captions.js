// captions.js: live captions over any surface (WORLD_CLASS_PLAN 28.5 row 9,
// Brief 82). Lazy (`LAZY_MODULES.captions`), reached from the palette's
// "Live captions" row, which starts them or, while they run, stops them.
//
// The page owns the microphone: it decimates the stream to 16 kHz mono and
// posts about a quarter second of it at a time to /voice/captions/<id>/audio,
// one request in flight; the reply carries the line still being written and
// the last three committed ones. The window, the helper and the commit rule
// are the server's (ai/captions.py). Stop saves the whole transcript as a
// note, and the dock's Copy takes the same text.
//
// The pipeline is timed on every reply (`captionRun.timing`: when the reply
// arrived, when its text was painted) so scratchpad/ui-sweeps/captions82.js
// can measure the page's own share of the speech-to-caption budget.

(() => {
  const CAPTION_RATE = 16000;
  const CAPTION_SEND_EVERY_MS = 250;
  //: Under the server's 64 KiB ceiling (32,000 samples) with room to spare.
  const CAPTION_MAX_SAMPLES = 24000;

  const captionRun = {
    id: "",
    stream: null,
    ctx: null,
    node: null,
    tick: 0,
    pending: [],
    sending: false,
    carry: { acc: 0, n: 0, pos: 0 },
    lines: [],
    running: "",
    model: "",
    elapsed: 0,
    timing: [],
    //: When the first audio block reached the page, for the latency sweep.
    firstAudioAt: 0,
    //: **Lent to the recorder** (UI_MODERNISATION V5): its stream, not ours to
    //: stop (`shared`); a painter in the dialog instead of the dock (`into`);
    //: no note on stop (`save`), the recording's own transcript is the record;
    //: and Pause (`held`) drops audio rather than captioning a pause.
    shared: false,
    into: null,
    save: true,
    held: false,
  };

  //: **Translate under the captions** (libr-1011 row 1222). Every finished line
  //: goes through the offline translator's worker (`translateAsk`, translate.js,
  //: loaded on the first press) one at a time, in order, and the last two sit
  //: under the running line. The note Stop saves keeps what was said; only the
  //: dock shows the other language. `out` is by line position, like `lines`.
  const captionTranslate = { on: false, pair: null, out: [], busy: false };

  function captionTranslatedText() {
    return captionTranslate.out.filter(Boolean).slice(-2).join("\n");
  }

  async function captionTranslatePump() {
    if (!captionTranslate.on || captionTranslate.busy || !captionRun.id) return;
    const at = captionTranslate.out.length;
    if (at >= captionRun.lines.length) return;
    captionTranslate.busy = true;
    try {
      const answer = await translateAsk(captionTranslate.pair, captionRun.lines[at]);
      //: A failed line keeps its place (an empty string), so the rest stay in step.
      captionTranslate.out[at] = answer?.ok ? String(answer.text || "").trim() : "";
    } catch {
      captionTranslate.out[at] = "";
    } finally {
      captionTranslate.busy = false;
    }
    captionPaint();
    captionTranslatePump();
  }

  async function captionToggleTranslate() {
    const button = $("captions-translate");
    if (captionTranslate.on) {
      captionTranslate.on = false;
    } else {
      await ensureModule("translate");
      const status = await apiJson("/translate/status", { silent: true }).catch(() => null);
      if (!status?.installed || !status.pairs?.length) {
        toast(status?.hint || "Translate needs the offline translator, in Settings, Packages.", "info");
        return;
      }
      //: The two lines the dock shows are translated at once; older ones are not.
      Object.assign(captionTranslate, { on: true, pair: status.pairs.find((p) => `${p.from}-${p.to}` === prefs.get("translate-pair")) || status.pairs[0], out: captionRun.lines.slice(0, -2).map(() => ""), busy: false });
    }
    button.setAttribute("aria-pressed", String(captionTranslate.on));
    $("captions-dock").classList.toggle("is-translating", captionTranslate.on);
    captionPaint();
    captionTranslatePump();
  }

  function captionsText() {
    return [...captionRun.lines, captionRun.running].filter(Boolean).join("\n");
  }

  //: Box-average decimation to 16 kHz, carried across blocks so no sample is
  //: dropped or doubled at a seam. An AudioContext at 16 kHz would do this
  //: natively, but Firefox refuses to connect a stream clocked at another rate
  //: to one.
  function captionDecimate(input, rate) {
    const ratio = rate / CAPTION_RATE;
    const out = [];
    const c = captionRun.carry;
    for (let i = 0; i < input.length; i++) {
      c.acc += input[i];
      c.n++;
      c.pos++;
      if (c.pos >= ratio) {
        const v = Math.max(-1, Math.min(1, c.acc / c.n));
        out.push(v < 0 ? v * 0x8000 : v * 0x7fff);
        c.acc = 0;
        c.n = 0;
        c.pos -= ratio;
      }
    }
    return Int16Array.from(out);
  }

  function captionPaint() {
    if (captionRun.into) return captionRun.into(captionRun.lines, captionRun.running);
    const past = $("captions-past");
    past.textContent = captionRun.lines.slice(-3).join("\n");
    $("captions-running").textContent = captionRun.running;
    const seconds = Math.floor(captionRun.elapsed / 1000);
    const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    $("captions-meta").textContent = `${captionRun.model} · ${clock}`;
    $("captions-copy").disabled = !captionsText();
    const translated = $("captions-translated");
    translated.textContent = captionTranslate.on ? captionTranslatedText() : "";
    translated.classList.toggle("hidden", !captionTranslate.on);
    if (captionTranslate.on) translated.lang = captionTranslate.pair.to;
  }

  async function captionSendNext() {
    if (captionRun.sending || !captionRun.id) return;
    let samples = 0;
    const take = [];
    while (captionRun.pending.length && samples < CAPTION_MAX_SAMPLES) {
      const block = captionRun.pending.shift();
      take.push(block);
      samples += block.length;
    }
    if (!samples) return;
    const body = new Int16Array(samples);
    let at = 0;
    for (const block of take) {
      body.set(block, at);
      at += block.length;
    }
    captionRun.sending = true;
    try {
      const reply = await apiJson(`/voice/captions/${captionRun.id}/audio`, {
        method: "POST",
        body: body.buffer,
        headers: { "Content-Type": "application/octet-stream" },
        readOnly: true,
        silent: true,
      });
      if (!captionRun.id) return;
      const replyAt = performance.now();
      captionRunMerge(reply);
      captionTranslatePump();
      captionRun.running = reply.running || "";
      captionRun.elapsed = reply.elapsed_ms || 0;
      requestAnimationFrame(() => {
        captionPaint();
        captionRun.timing.push({ replyAt, paintedAt: performance.now(), text: captionRun.running });
      });
      if (!captionRun.into) {
        $("captions-dock").classList.toggle("is-error", !!reply.error);
        if (reply.error) $("captions-running").textContent = captionRun.running || "The captions helper is not answering.";
      }
      if (reply.stopped) stopLiveCaptions();
    } catch (error) {
      if (!captionRun.id) return;
      toast(error.message || "Live captions stopped.", true);
      stopLiveCaptions();
    } finally {
      captionRun.sending = false;
    }
  }

  //: The server sends the last three committed lines and how many it has
  //: committed in all, so the page keeps every line by position (matching the
  //: text instead would swallow a line said twice).
  function captionRunMerge(reply) {
    const first = reply.count - reply.lines.length;
    reply.lines.forEach((line, i) => {
      if (first + i >= captionRun.lines.length) captionRun.lines.push(line);
    });
  }

  //: `opts` (V5): `stream` lends a live stream, `into(lines, running)` paints
  //: somewhere other than the dock, `save: false` keeps no note, `quiet`
  //: returns the reason instead of a toast. Resolves true once running.
  async function startLiveCaptions(opts = {}) {
    if (captionRun.id) return opts.quiet ? "Live captions are already running." : false;
    const status = await apiJson("/voice/status", { silent: true }).catch(() => null);
    const info = status?.captions;
    if (!info?.available) {
      const why = info?.hint || "Live captions aren't available.";
      if (opts.quiet) return why;
      toast(why, "info");
      return false;
    }
    let stream = opts.stream;
    if (!stream) {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraints() });
      } catch {
        toast("Microphone access was blocked, allow it in your browser.", "info");
        return false;
      }
    }
    //: The installed helper starts on this first use and the start answers when
    //: it does (a second or two; up to 15 s on a slow disk), so say so.
    if (info.starts_on_first_use && !opts.quiet) toast("Starting captions…", "info");
    let started;
    try {
      //: The audio is kept only when asked for (Settings, General, Microphone) and only for a run of
      //: the captions' own: the recorder lends its stream and keeps its own recording.
      started = await apiJson("/voice/captions/start", { method: "POST", body: JSON.stringify({ keep_audio: !opts.stream && prefs.bool("captionsKeepAudio", false) }) });
    } catch (error) {
      if (!opts.stream) stream.getTracks().forEach((t) => t.stop());
      if (opts.quiet) return error.message;
      toast(error.message, true);
      return false;
    }
    Object.assign(captionRun, { id: started.id, stream, lines: [], running: "", model: started.model, elapsed: 0, pending: [], timing: [], firstAudioAt: 0, shared: !!opts.stream, into: opts.into || null, save: opts.save !== false, held: false });
    Object.assign(captionRun.carry, { acc: 0, n: 0, pos: 0 });
    const ctx = new AudioContext();
    //: The tap is an AudioWorklet (L580), loaded as a module from the app's own
    //: origin, which `script-src 'self'` allows, so the policy has no blob: or
    //: data: URL to permit. It sends 4096-sample blocks, as ScriptProcessor did.
    let node;
    try {
      await ctx.audioWorklet.addModule("/js/caption-tap-worker.js");
      node = new AudioWorkletNode(ctx, "caption-tap", { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1 });
    } catch (error) {
      ctx.close().catch(() => {});
      if (!opts.stream) stream.getTracks().forEach((t) => t.stop());
      apiJson(`/voice/captions/${started.id}/stop`, { method: "POST", body: JSON.stringify({ save: false }), silent: true }).catch((e) => console.warn("The caption take was not stopped:", e.message));
      const why = `Live captions couldn't start the microphone tap. ${error.message || ""}`.trim();
      if (opts.quiet) return why;
      toast(why, "info");
      return false;
    }
    node.port.onmessage = (e) => {
      if (captionRun.held) return;
      if (!captionRun.firstAudioAt) captionRun.firstAudioAt = performance.now();
      captionRun.pending.push(captionDecimate(e.data, ctx.sampleRate));
    };
    const source = ctx.createMediaStreamSource(stream);
    const mute = ctx.createGain();
    mute.gain.value = 0;
    source.connect(node);
    node.connect(mute);
    mute.connect(ctx.destination);
    Object.assign(captionRun, { ctx, node });
    captionRun.tick = setInterval(captionSendNext, CAPTION_SEND_EVERY_MS);
    if (!captionRun.into) {
      $("captions-dock").classList.remove("hidden", "is-error", "is-translating");
      Object.assign(captionTranslate, { on: false, pair: null, out: [], busy: false });
      $("captions-translate").setAttribute("aria-pressed", "false");
      captionOfferTranslate();
    }
    captionPaint();
    return true;
  }

  //: The Translate button shows only when the offline translator is installed,
  //: so a press never lands on "needs a package".
  function captionOfferTranslate() {
    apiJson("/translate/status", { silent: true })
      .then((status) => $("captions-translate").classList.toggle("hidden", !(status?.installed && status.pairs?.length)))
      .catch(() => {});
  }

  function captionRelease() {
    clearInterval(captionRun.tick);
    if (!captionRun.shared) captionRun.stream?.getTracks().forEach((t) => t.stop());
    if (captionRun.node) captionRun.node.port.onmessage = null;
    captionRun.ctx?.close().catch(() => {});
    Object.assign(captionRun, { stream: null, ctx: null, node: null, tick: 0, pending: [], shared: false, held: false });
  }

  async function stopLiveCaptions() {
    const id = captionRun.id;
    if (!id) return;
    captionRelease();
    captionRun.id = "";
    if (!captionRun.save) {
      captionRun.into = null;
      captionRun.save = true;
      const done = await apiJson(`/voice/captions/${id}/stop`, { method: "POST", body: JSON.stringify({ save: false }), silent: true }).catch((e) => console.warn("The caption take was not stopped:", e.message) || null);
      return done?.text || "";
    }
    $("captions-dock").classList.add("hidden");
    captionTranslate.on = false;
    try {
      const done = await apiJson(`/voice/captions/${id}/stop`, { method: "POST", body: "{}" });
      if (!done.entry_id) {
        toast("Nothing was said, so nothing was saved.");
        return;
      }
      await refreshEntries([done.entry_id]);
      flashEntry(done.entry_id);
      toastAction(
        done.recording_id ? "Saved the captions as a note, and the audio in Recordings." : "Saved the captions as a note.",
        "Open",
        () => flashEntry(done.entry_id)
      );
    } catch (error) {
      toast(error.message || "Couldn't save the captions.", true);
    }
  }

  //: The recorder's live words end with its take (V5); a captions run of
  //: one's own, from the palette or a Captions button, is left alone.
  function stopRecorderWords() {
    if (captionRun.id && captionRun.into) return stopLiveCaptions();
  }

  function holdLiveCaptions(on) {
    captionRun.held = !!on;
  }

  function toggleLiveCaptions() {
    return captionRun.id ? stopLiveCaptions() : startLiveCaptions();
  }

  $("captions-stop").addEventListener("click", stopLiveCaptions);
  $("captions-translate").addEventListener("click", captionToggleTranslate);
  $("captions-copy").addEventListener("click", () => copyToClipboard(captionsText(), $("captions-copy")));

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { holdLiveCaptions, startLiveCaptions, stopRecorderWords, toggleLiveCaptions });
})();
