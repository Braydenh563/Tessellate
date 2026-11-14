// studio.js: the offline studio and the natural voice's reading (WORLD_CLASS_PLAN rows 35 and 37, Q34).
// Lazy (LAZY_MODULES.studio in lazy-entries.js): the palette's "Make an audio overview" opens the sheet, and
// `speakText` (media.js) fetches this file the first time the natural voice is chosen in Settings, Read aloud.
//
// **Nothing here makes sound or words.** The sheet asks `POST /studio/overview` (the notes' own sentences under a
// fixed frame, spoken by Piper on this computer, saved as a recording) and follows the run; reading aloud posts
// the text to `POST /voice/speak` and plays the wav it gets back. Both need the Natural voice package
// (Settings, Packages); without it the sheet says so and the browser's voices keep reading.
(() => {
  const POLL_MS = 700;
  //: One reading at a time, held on the function (the global-scope ratchet): the clip playing, if any.
  const reading = { audio: null, url: "" };

  function stopReading() {
    if (!reading.audio) return false;
    reading.audio.pause();
    URL.revokeObjectURL(reading.url);
    const done = reading.audio.onended;
    reading.audio = null;
    done?.();
    return true;
  }

  //: Read `text` in the natural voice. `handle` is the object `speakText` gave its caller, whose `onstart` and `onend`
  //: are set after this returns (a message's Read aloud turns to Stop reading); a press while it reads stops it.
  async function speakNatural(text, button = null, handle = {}) {
    if (stopReading()) return;
    const paint = (on) => {
      if (!button) return;
      button.setAttribute("aria-pressed", on);
      if (on) setLabel(button, "ph:stop");
      else setLabel(button, "ph:speaker-high");
    };
    try {
      const response = await api("/voice/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      reading.url = URL.createObjectURL(await response.blob());
      reading.audio = new Audio(reading.url);
      reading.audio.onended = () => {
        paint(false);
        handle.onend?.();
        if (reading.audio) {
          URL.revokeObjectURL(reading.url);
          reading.audio = null;
        }
      };
      paint(true);
      handle.onstart?.();
      await reading.audio.play();
    } catch (error) {
      paint(false);
      handle.onerror?.();
      toast(error.message || voiceLine("failed", { what: "read that aloud" }), true);
    }
  }

  function field(labelText, control) {
    const label = document.createElement("label");
    label.className = "row space-between setting-row";
    const word = document.createElement("span");
    word.textContent = labelText;
    label.append(word, control);
    return label;
  }

  function openStudio() {
    openSheet({
      label: "Make an audio overview",
      sub: "Your notes, read aloud in a natural voice, saved as a recording.",
      name: "studio",
      build: (card, close) => {
        const topic = document.createElement("input");
        topic.type = "text";
        topic.maxLength = 120;
        topic.placeholder = "All recent notes";
        topic.setAttribute("aria-label", "Topic");
        const minutes = document.createElement("select");
        minutes.setAttribute("aria-label", "Length");
        for (const [value, name] of [["1", "About 1 minute"], ["3", "About 3 minutes"], ["5", "About 5 minutes"]]) {
          minutes.add(new Option(name, value, false, value === "3"));
        }
        const brief = document.createElement("input");
        brief.type = "checkbox";
        brief.id = "studio-brief";
        const briefLabel = document.createElement("label");
        briefLabel.className = "checkbox-label";
        briefLabel.append(brief, " A brief before a meeting");
        const status = document.createElement("p");
        status.className = "muted";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        const make = smallButton("ph:waveform Make it", "Make the overview from the notes that hold the topic", () => start(), false);
        const stop = smallButton("ph:stop Stop", "Stop making it", () => {}, true);
        stop.classList.add("hidden");
        const actions = document.createElement("div");
        actions.className = "row";
        actions.append(make, stop);
        card.append(field("About", topic), field("Length", minutes), briefLabel, actions, status);
        topic.focus();

        const follow = async (id) => {
          stop.onclick = () => api(`/studio/runs/${id}/stop`, { method: "POST" }).catch(() => { status.textContent = "Couldn't stop it. Try again."; });
          for (;;) {
            await new Promise((resolve) => setTimeout(resolve, POLL_MS));
            const run = await apiJson(`/studio/runs/${id}`);
            if (run.state === "running") {
              status.textContent = `Reading it into a recording, ${Math.round((run.progress || 0) * 100)}% done`;
              continue;
            }
            return run;
          }
        };
        const start = async () => {
          make.disabled = true;
          status.textContent = "Reading your notes";
          try {
            const run = await apiJson("/studio/overview", {
              method: "POST",
              body: JSON.stringify({ topic: topic.value.trim(), minutes: Number(minutes.value), brief: brief.checked }),
            });
            stop.classList.remove("hidden");
            const end = await follow(run.id);
            stop.classList.add("hidden");
            if (end.state === "done") {
              close();
              toastAction(`Made “${run.title}”.`, "Open", () => ensureModule("meetings").then(() => openRecordings(end.recording_id)));
              return;
            }
            status.textContent = end.state === "stopped" ? "Stopped. Nothing was kept." : end.error;
          } catch (error) {
            stop.classList.add("hidden");
            status.textContent = error.message;
          }
          make.disabled = false;
        };
      },
    });
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { openStudio, speakNatural });
})();
