// The model bench in Settings, Models (WORLD_CLASS_PLAN I8, H3).
//
// Loaded on the first open of the Models section (settings.js,
// `showSettingsSection`), never at boot. The bench itself is ai/bench.py,
// behind `/models/bench` (routes_bench.py); this file draws the choice of
// models, the Run and Stop pair, and the report: one row per model, best
// first, its numbers on a facts line and the first failures under it, so the
// recommendation can be checked rather than trusted. "Use this one" is the
// same `POST /models/chat-model` the model picker calls.

const benchPoll = { timer: null };

function benchPercent(value) {
  return value === null || value === undefined ? "–" : `${Math.round(value * 100)}%`;
}

function benchFailureText(failure) {
  const what = { filing: "Filing", citation: "Answer", tools: "Tool call" }[failure.task] || failure.task;
  return `${what}: expected ${failure.expected}, got ${failure.got || "nothing"}`;
}

function benchRow(row, recommended, chatModel) {
  const li = document.createElement("li");
  li.className = "bench-row";
  const body = document.createElement("div");
  body.className = "bench-row-body";
  const title = document.createElement("div");
  title.className = "bench-row-title";
  const name = document.createElement("span");
  name.textContent = row.model;
  title.append(name);
  if (row.model === recommended) title.append(chip("Recommended", "item-label is-ok"));
  if (row.model === chatModel) title.append(chip("In use for chat", "item-label is-yours"));
  const facts = document.createElement("p");
  facts.className = "library-file-meta bench-row-meta";
  const parts = [
    `Filing ${benchPercent(row.filing)}`,
    `Answers ${benchPercent(row.citation)}`,
    `Tools ${benchPercent(row.tools)}`,
  ];
  if (row.answer_ms !== null && row.answer_ms !== undefined) parts.push(`${(row.answer_ms / 1000).toFixed(1)} s an answer`);
  if (row.tokens) parts.push(`${row.tokens} tokens`);
  if (row.errors) parts.push(`${row.errors} failed call${row.errors === 1 ? "" : "s"}`);
  facts.textContent = parts.join(" · ");
  body.append(title, facts);
  if (row.failures && row.failures.length) {
    const list = document.createElement("ul");
    list.className = "bench-failures muted text-sm";
    for (const failure of row.failures.slice(0, 3)) {
      const item = document.createElement("li");
      item.textContent = benchFailureText(failure);
      item.title = failure.question || "";
      list.append(item);
    }
    body.append(list);
  }
  const actions = document.createElement("div");
  actions.className = "bench-row-actions";
  if (row.model !== chatModel) {
    const use = document.createElement("button");
    use.type = "button";
    use.className = "ghost small";
    use.textContent = "Use this one";
    use.addEventListener("click", async () => {
      use.disabled = true;
      try {
        await apiJson("/models/chat-model", { method: "POST", body: JSON.stringify({ name: row.model }) });
        toast(`${row.model} now answers in chat.`);
        renderModelBench();
      } catch (error) {
        toast(error.message || "Couldn't switch the chat model.", true);
        use.disabled = false;
      }
    });
    actions.append(use);
  }
  li.append(body, actions);
  return li;
}

function benchShowReport(report, chatModel) {
  const host = $("bench-results");
  host.replaceChildren();
  if (!report || !report.models || !report.models.length) return;
  for (const row of report.models) host.append(benchRow(row, report.recommended, chatModel));
}

function benchStatusLine(state) {
  if (state.running) {
    const p = state.progress;
    return p ? `ph:spin Testing ${p.model}, task ${p.done + 1} of ${p.total}…` : "ph:spin Starting…";
  }
  const report = state.report;
  if (!report) return "";
  if (report.stopped === "budget") return `Stopped at the time limit after ${report.seconds} s, so no recommendation.`;
  if (report.stopped) return "Stopped, so no recommendation.";
  return `Tested on ${report.items} of your notes in ${Math.round(report.seconds)} s.`;
}

async function renderModelBench() {
  const box = $("bench-box");
  if (!box) return;
  let status;
  let state;
  try {
    [status, state] = await Promise.all([apiJson("/models/status", { cacheMs: 600 }), apiJson("/models/bench")]);
  } catch {
    box.classList.add("hidden");
    return;
  }
  const installed = (status.installed_models || []).map((m) => m.name).filter((n) => n && !/embed/i.test(n));
  box.classList.toggle("hidden", !status.ollama_running || installed.length === 0 || !state.enabled);
  const picks = $("bench-models");
  const chosen = new Set([...picks.querySelectorAll("input:checked")].map((i) => i.value));
  if (!chosen.size) for (const name of installed.slice(0, 3)) chosen.add(name);
  picks.replaceChildren(
    ...installed.map((name) => {
      const label = document.createElement("label");
      label.className = "setting-check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = name;
      input.checked = chosen.has(name);
      const span = document.createElement("span");
      span.textContent = name;
      label.append(input, span);
      return label;
    })
  );
  $("bench-run").disabled = Boolean(state.running);
  $("bench-stop").classList.toggle("hidden", !state.running);
  setLabel($("bench-status"), benchStatusLine(state));
  benchShowReport(state.report, status.chat_model);
  clearTimeout(benchPoll.timer);
  if (state.running && !box.closest(".hidden")) benchPoll.timer = setTimeout(renderModelBench, 1500);
}

async function runModelBench() {
  const models = [...$("bench-models").querySelectorAll("input:checked")].map((i) => i.value);
  if (!models.length) {
    setLabel($("bench-status"), "Pick at least one model to test.");
    return;
  }
  $("bench-run").disabled = true;
  try {
    await apiJson("/models/bench", { method: "POST", body: JSON.stringify({ models }) });
  } catch (error) {
    $("bench-status").textContent = error.message || "Couldn't start the test.";
    $("bench-run").disabled = false;
    return;
  }
  renderModelBench();
}

$("bench-run")?.addEventListener("click", runModelBench);
$("bench-stop")?.addEventListener("click", () => {
  apiJson("/models/bench/stop", { method: "POST" })
    .catch((error) => toast(error.message || "Couldn't stop the bench.", true))
    .finally(renderModelBench);
});
