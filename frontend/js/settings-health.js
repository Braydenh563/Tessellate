// settings-health.js: Settings, About's health block and the sampling rows, moved out of settings.js on 2026-10-12 for the boot gzip budget. Drawn when their pane opens; `LAZY_ENTRY_POINTS.settingsHealth` (app.js) stands in.

async function renderHealthBlock() {
  const dbSize = $("health-db-size");
  const counts = $("health-counts");
  const jobs = $("health-jobs");
  const lastError = $("health-last-error");
  const latency = $("health-latency");
  if (!dbSize || !counts || !jobs || !lastError) return; // markup not present yet
  const health = await apiJson("/debug/health", { silent: true }).catch(() => null);
  if (!health) {
    // The endpoint itself is one more thing that can be down (offline
    // build, a locked notebook mid-request), a dash across the board reads
    // as "couldn't check", not "empty", so nothing here claims a zero it
    // never actually measured.
    for (const el of [dbSize, counts, jobs, lastError, latency]) if (el) el.textContent = ", ";
    return;
  }
  dbSize.textContent = `${formatFileSize(health.db?.size_bytes) || "0 B"} · ${health.data_dir}`;
  //: Where the space goes, as a bar (settings-data.js): a second request, kept
  //: apart from health so a slow walk never delays the numbers above.
  ensureModule("settingsData").then(() => renderStorageBreakdown());
  const c = health.counts || {};
  //: Each kind counted as the rest of the app counts it: notes are the
  //: dashboard's notes (no boards, no drafts), and boards and drafts are
  //: named rather than folded in (it read "96 notes" beside a dashboard's 44).
  //: A kind with none is left out, and "1 draft" is singular.
  const parts = [nounCount(c.notes ?? c.entries ?? 0, "note", "notes")];
  if (c.drafts) parts.push(nounCount(c.drafts, "draft", "drafts"));
  if (c.boards) parts.push(nounCount(c.boards, "board or map", "boards and maps"));
  parts.push(nounCount(c.documents ?? 0, "document", "documents"));
  if (c.media) parts.push(nounCount(c.media, "file", "files"));
  if (c.attachments) parts.push(nounCount(c.attachments, "attachment", "attachments"));
  parts.push(nounCount(c.reminders ?? 0, "reminder", "reminders"));
  counts.textContent = parts.join(" · ");
  //: Rule 14 (WORLD_CLASS_PLAN 28.1): each field present and dated.
  const trust = health.trust || {};
  const when = (iso) => (iso ? `${relativeTime(iso)} (${whenText(iso)})` : "");
  const asOf = ` as of ${new Date(trust.checked_at || Date.now()).toLocaleTimeString()}`;
  $("health-checked").textContent = `Checked${asOf}.`;
  const backup = trust.last_backup || {};
  $("health-last-backup").textContent = backup.at ? `${when(backup.at)} · ${backup.name}` : `No backup yet${asOf}`;
  //: A first count cut short (the folder is large) says "or more"; the next check has the whole.
  $("health-data-dir").textContent = `${formatFileSize(trust.data_dir_bytes) || "0 B"}${trust.data_dir_bytes_partial ? " or more" : ""}${asOf}`;
  paintIntegrity(trust.integrity);
  const running = trust.running || health.jobs?.running || [];
  jobs.textContent = (running.length ? running.map((job) => job.label).join(", ") : "Nothing running") + asOf;
  const last = trust.last_error || {};
  lastError.textContent = last.at ? `${when(last.at)} · ${last.line}` : `None recorded${asOf}`;
  // PLAN B9's p50/p95, per task kind. The endpoint carried them from the
  // start; the block did not draw them (BACKLOG §116.1 item 2). Seconds with
  // one decimal, because a caption takes 3.2s and a re-index 40s, and "3210
  // ms" is a number nobody reads at a glance.
  //: What the search engine has to work with. Its own route says the Settings
  //: page wants this and the Settings page had never asked; it answers the
  //: question behind every "search did not find my note", which is whether
  //: the note is in the index at all and whether the vectors are warm. Kinds
  //: with nothing in them are left out: six zeroes say less than the two
  //: numbers that are not.
  const search = $("health-search");
  if (search) {
    const stats = await apiJson("/search/stats", { silent: true }).catch(() => null);
    if (!stats) search.textContent = ", ";
    else {
      const kinds = Object.entries(stats.index || {})
        .filter(([, n]) => n > 0)
        .map(([kind, n]) => `${n} ${kind}${n === 1 ? "" : "s"}`);
      const vectors = stats.vectors
        ? `${stats.vectors} vectors${stats.vectors_warm ? "" : " (not loaded yet)"}`
        : "no vectors yet, keyword search only";
      search.textContent = `${kinds.length ? kinds.join(" \u00b7 ") : "nothing indexed yet"} \u00b7 ${vectors}`;
    }
  }
  if (latency) {
    const secs = (ms) => `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)}s`;
    const rows = Object.entries(health.latency_ms_by_kind || {})
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([kind, stat]) => `${kind}: ${secs(stat.p50_ms)} typical, ${secs(stat.p95_ms)} slow (${stat.count})`);
    latency.textContent = rows.length ? rows.join(" · ") : "No timed jobs yet";
  }
}

function renderSamplingRows() {
  const host = $("sampling-rows");
  if (!host || !samplingState) return;
  host.replaceChildren();

  $("sampling-model").textContent = samplingState.model
    ? `Showing what ${samplingState.model} recommends for itself.`
    : "";
  // The OpenAI-compatible dialect has no endpoint that reports a model's own
  // parameters, and accepts only temperature and top-p. Saying so beats a
  // panel that silently does less than it appears to.
  $("sampling-note").textContent = samplingState.reports_model_defaults
    ? ""
    : "This backend doesn't report what a model recommends, so these start at "
      + "the server's defaults. Only temperature and top-p are sent to an "
      + "OpenAI-compatible server.";

  for (const knob of samplingState.knobs) {
    const row = document.createElement("div");
    row.className = "sampling-row";

    const head = document.createElement("div");
    head.className = "row space-between";
    const label = document.createElement("label");
    label.className = "sampling-label";
    label.textContent = knob.label;
    label.htmlFor = `sampling-${knob.name}`;
    const source = document.createElement("span");
    source.className = "chip item-label sampling-source";
    head.append(label, source);

    const help = document.createElement("p");
    help.className = "muted text-sm";
    help.textContent = knob.help;

    const controls = document.createElement("div");
    controls.className = "row gap sampling-controls";
    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = `sampling-${knob.name}`;
    slider.min = knob.min;
    slider.max = knob.max;
    slider.step = knob.step;
    const readout = document.createElement("output");
    readout.className = "sampling-value";
    //: **A number you can type, beside the one you can drag.**
    //:
    //: Reported: the advanced response settings "don't work". They do: a
    //: change persists and reaches the model (verified against
    //: `GET /models/sampling` after a change): but a slider alone cannot
    //: express the thing anyone opening this panel came to do: set
    //: temperature to exactly 0.7 because a model card said so. At a step of
    //: 0.05 across 0–2 that is a 40-position drag with no way to confirm the
    //: value except by reading it back, which is indistinguishable from a
    //: control that ignores you.
    const number = document.createElement("input");
    number.type = "number";
    number.className = "sampling-number";
    number.id = `sampling-${knob.name}-value`;
    number.min = knob.min;
    number.max = knob.max;
    number.step = knob.step;
    number.setAttribute("aria-label", `${knob.label}: type an exact value`);
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "ghost small icon-button";
    setLabel(reset, "ph:arrow-counter-clockwise");
    reset.title = `Use what ${samplingState.model || "the model"} recommends`;
    reset.setAttribute("aria-label", reset.title);

    const paint = () => {
      const overridden = knob.name in samplingState.overrides;
      const value = samplingState.effective[knob.name];
      // No value from any layer means the backend's own default, which is a
      // real state and not zero, the slider has to show *something*, so it
      // sits at the midpoint and the label says the number is not ours.
      const shown = value === undefined
        ? (Number(knob.min) + Number(knob.max)) / 2
        : value;
      slider.value = shown;
      //: Blank rather than the midpoint when nothing is set: a number in the
      //: box would claim the app had chosen a value it has not.
      number.value = value === undefined ? "" : String(value);
      number.placeholder = value === undefined ? "auto" : "";
      //: The number field already shows the value; the readout only speaks
      //: when there is none (INBOX 437: "124" twice on one row).
      readout.textContent = value === undefined ? "backend default" : "";
      readout.classList.toggle("hidden", value !== undefined);
      const from = samplingState.sources[knob.name];
      source.textContent =
        from === "you" ? "you set this" : from === "model" ? "from the model" : "default";
      source.classList.toggle("is-yours", overridden);
      reset.disabled = !overridden;
    };
    paint();
    //: Double-click means "back to the model's", the reset button's meaning.
    slider.addEventListener("rangereset", (event) => {
      event.preventDefault();
      if (!reset.disabled) reset.click();
    });

    // Dragging a slider fires `input` on every pixel. Saved on a trailing
    // timer rather than per event, the same shape every other debounced
    // control in this app uses, since there is no shared helper.
    const save = () => {
      clearTimeout(samplingSaveTimer);
      samplingSaveTimer = setTimeout(async () => {
        try {
          await apiJson("/models/sampling", {
            method: "PUT",
            body: JSON.stringify({ overrides: samplingState.overrides }),
          });
        } catch {
          toast("Couldn't save that setting.", true);
        }
        await loadSamplingSettings();
      }, 400);
    };

    //: One place that applies a value, so the slider and the box cannot
    //: disagree about what "set" means (rounding, the integer knobs, which
    //: layer the value came from).
    const applyValue = (raw) => {
      const clamped = Math.min(Math.max(raw, Number(knob.min)), Number(knob.max));
      const value = knob.integer ? Math.round(clamped) : Number(clamped.toFixed(4));
      samplingState.overrides[knob.name] = value;
      samplingState.effective[knob.name] = value;
      samplingState.sources[knob.name] = "you";
      paint();
      save();
    };

    slider.addEventListener("input", () => applyValue(Number(slider.value)));
    //: `change`, not `input`: typing "0.7" passes through "0." and "0", and
    //: saving each keystroke would both spam the endpoint and fight the
    //: caret. An empty box is "back to the model's own value", which is the
    //: same act as the reset button beside it.
    number.addEventListener("change", () => {
      if (number.value.trim() === "") {
        delete samplingState.overrides[knob.name];
        paint();
        save();
        return;
      }
      const raw = Number(number.value);
      if (Number.isFinite(raw)) applyValue(raw);
      else paint();
    });
    reset.addEventListener("click", async () => {
      // Deleting the override *is* the reset, there is no separate stored
      // "default", which is what lets a different model bring its own.
      delete samplingState.overrides[knob.name];
      try {
        await apiJson("/models/sampling", {
          method: "PUT",
          body: JSON.stringify({ overrides: samplingState.overrides }),
        });
      } catch {
        toast("Couldn't reset that setting.", true);
      }
      await loadSamplingSettings();
    });

    controls.append(slider, number, readout, reset);
    row.append(head, help, controls);
    host.appendChild(row);
  }
}
