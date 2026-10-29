// dash-night.js: the dashboard's "While you were away" card (what Atlas worked out on its own, one row per finding), moved out of dashboard.js on 2026-10-12 for the boot gzip budget. The widget table's `render` calls `renderNightWidget` for its effect: `LAZY_ENTRY_POINTS.dashNight` (app.js) stands in.

function nightKindWords(kind, n) {
  const [one, many] = NIGHT_KIND_WORDS[kind] || [kind, `${kind}s`];
  return `${n} ${n === 1 ? one : many}`;
}

function nightRunSummary(run) {
  const read = `Read ${nounCount(run.scanned, "note")}`;
  const when = dashRelativeTime(run.finished_at || run.started_at);
  const stopped = run.stopped_reason === "budget" ? "stopped at its budget, carries on next time" : "";
  return [read, when, stopped].filter(Boolean).join(" · ");
}

function nightFactRow(fact, onGone) {
  const li = document.createElement("li");
  li.className = "night-fact";
  const text = document.createElement("span");
  text.className = "dash-list-text";
  const title = document.createElement("span");
  title.className = "dash-list-title night-fact-text";
  title.textContent = fact.text;
  const meta = document.createElement("span");
  meta.className = "dash-list-preview";
  meta.textContent = [fact.model === "local" ? "Found without a model" : fact.model, `${Math.round((fact.confidence || 0) * 100)}% sure`]
    .filter(Boolean)
    .join(" · ");
  text.append(title);
  //: A pair quotes its other side; the reason joins the facts.
  if (fact.pair && NIGHT_PAIR_LEAD[fact.kind]) {
    const other = document.createElement("span");
    other.className = "dash-list-preview night-fact-pair";
    other.textContent = `${NIGHT_PAIR_LEAD[fact.kind]}: “${fact.pair.text || ""}”`;
    text.append(other);
    if (fact.pair.reason) meta.textContent = [fact.pair.reason, meta.textContent].join(" · ");
  }
  text.append(meta);
  const actions = document.createElement("span");
  actions.className = "night-fact-actions";
  if (fact.pair && fact.pair.entry_id) {
    const openOther = document.createElement("button");
    openOther.type = "button";
    openOther.className = "ghost small icon-only";
    const otherLabel = fact.kind === "answered" ? "Open the note with the question" : "Open the other note";
    openOther.title = otherLabel;
    openOther.setAttribute("aria-label", otherLabel);
    setLabel(openOther, "ph:arrows-left-right");
    openOther.addEventListener("click", () => flashEntry(fact.pair.entry_id));
    actions.append(openOther);
  }
  //: Accept a tension: the `contradicts` link (I1, the existing accept path).
  if (fact.kind === "tension" && fact.pair && fact.pair.entry_id) {
    const keep = document.createElement("button");
    keep.type = "button";
    keep.className = "ghost small icon-only";
    keep.title = "Link the two notes as disagreeing";
    keep.setAttribute("aria-label", "Link the two notes as disagreeing");
    setLabel(keep, "ph:link");
    keep.addEventListener("click", async () => {
      keep.disabled = true;
      try {
        const done = await apiJson("/entries/tensions/accept", {
          method: "POST",
          body: JSON.stringify({ earlier_id: fact.pair.entry_id, later_id: fact.entry_id }),
        });
        pushTensionLinkUndo(fact.pair.entry_id, fact.entry_id, "accept", done?.created !== false);
        toast("Linked as disagreeing");
      } catch (error) {
        keep.disabled = false;
        toast(error.message || "Couldn't link those notes.", true);
      }
    });
    actions.append(keep);
  }
  const open = document.createElement("button");
  open.type = "button";
  open.className = "ghost small icon-only";
  open.title = "Open the note this came from";
  open.setAttribute("aria-label", "Open the note this came from");
  setLabel(open, "ph:arrow-square-out");
  open.addEventListener("click", () => flashEntry(fact.entry_id));
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "ghost small icon-only";
  dismiss.title = "Dismiss, and never work this out again";
  dismiss.setAttribute("aria-label", "Dismiss, and never work this out again");
  setLabel(dismiss, "ph:x");
  dismiss.addEventListener("click", async () => {
    dismiss.disabled = true;
    try {
      await api(`/learned/${fact.id}`, { method: "DELETE" });
      pushRoutePairUndo("Dismissed a learned thing", [`/learned/${fact.id}/restore`, "POST"], [`/learned/${fact.id}`, "DELETE"], () => renderDashboard({ refresh: true }));
      li.remove();
      onGone();
    } catch (error) {
      dismiss.disabled = false;
      toast(error.message || "Couldn't dismiss that.", true);
    }
  });
  actions.append(open, dismiss);
  li.append(text, actions);
  return li;
}

//: One line of the card: the count, a disclosure that opens the review list
//: under it. The list pages by NIGHT_PAGE; "Show more" reads the next page.
function nightKindLine(host, runId, kind, count) {
  const li = document.createElement("li");
  li.className = "night-kind";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ghost small disclosure-row night-kind-toggle";
  toggle.setAttribute("aria-expanded", "false");
  const label = () => setLabel(toggle, `ph:caret-right ${nightKindWords(kind, count)}`);
  label();
  const list = document.createElement("ul");
  list.className = "dash-list night-facts hidden";
  list.id = `night-facts-${runId}-${kind}`;
  toggle.setAttribute("aria-controls", list.id);
  const more = document.createElement("button");
  more.type = "button";
  more.className = "ghost small night-more hidden";
  more.textContent = "Show more";
  let offset = 0;
  let loaded = false;
  const gone = () => {
    count -= 1;
    offset = Math.max(0, offset - 1);
    label();
    if (count <= 0) li.remove();
  };
  const page = async () => {
    more.disabled = true;
    try {
      const reply = await apiJson(`/night/runs/${runId}/facts?kind=${encodeURIComponent(kind)}&limit=${NIGHT_PAGE}&offset=${offset}`, { silent: true });
      for (const fact of reply.items || []) list.appendChild(nightFactRow(fact, gone));
      offset += (reply.items || []).length;
      more.classList.toggle("hidden", offset >= (reply.total || 0));
    } catch (error) {
      toast(error.message || "Couldn't read that list.", true);
    } finally {
      more.disabled = false;
    }
  };
  toggle.addEventListener("click", async () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    list.classList.toggle("hidden", !open);
    if (open && !loaded) {
      loaded = true;
      await page();
    }
    if (!open) more.classList.add("hidden");
    else more.classList.toggle("hidden", offset >= count);
  });
  more.addEventListener("click", () => page());
  li.append(toggle, list, more);
  host.appendChild(li);
}

//: The card, then the open questions count and the oldest one (I3).
async function renderNightWidget(body) {
  await renderNightCard(body);
  let summary;
  try {
    summary = await apiJson("/questions/summary", { silent: true });
  } catch {
    return;
  }
  if (!summary || !summary.open) return;
  const line = document.createElement("p");
  line.className = "muted night-questions";
  const oldest = summary.oldest;
  const words = `${summary.open} open question${summary.open === 1 ? "" : "s"}`;
  //: `display` is the question without its markdown, as the Questions view
  //: shows it; `text` printed "**why**" with its stars (OPEN 1114's audit).
  line.textContent = oldest ? `${words}. The oldest: “${oldest.display || oldest.text}”` : `${words}.`;
  const open = document.createElement("button");
  open.type = "button";
  open.className = "ghost small";
  setLabel(open, "ph:question See your questions");
  open.addEventListener("click", async () => {
    await switchTab("notes");
    showNotesSection("questions");
  });
  const row = document.createElement("div");
  row.className = "row night-questions-row";
  row.append(line, open);
  body.appendChild(row);
}

async function renderNightCard(body) {
  let card;
  try {
    card = await apiJson("/night/latest", { silent: true });
  } catch {
    surfaceFailed(body, "what Atlas found", () => renderNightWidget(body));
    return;
  }
  if (!card.run) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const line = document.createElement("p");
    line.textContent = "Atlas has not read your notes on its own yet.";
    const run = document.createElement("button");
    run.type = "button";
    run.className = "ghost small";
    setLabel(run, "ph:moon-stars Read my notes now");
    run.addEventListener("click", async () => {
      run.disabled = true;
      try {
        const reply = await apiJson("/night/run", { method: "POST", body: JSON.stringify({}) });
        if (reply.paused) toast("Reading on its own is switched off in Settings, What it learned.");
      } catch (error) {
        toast(error.message, true);
      }
      body.replaceChildren();
      renderNightWidget(body);
    });
    empty.append(line, run);
    body.appendChild(empty);
    return;
  }
  const summary = document.createElement("p");
  summary.className = "muted night-summary";
  summary.textContent = nightRunSummary(card.run);
  body.appendChild(summary);
  let shown = card.run;
  let counts = card.counts || {};
  if (!Object.keys(counts).length) {
    if (!card.previous) {
      dashEmpty(body, "Nothing new since it last read. Claims, open questions and notes that disagree show up here.", null);
      return;
    }
    shown = card.previous;
    counts = card.previous.counts || {};
    const earlier = document.createElement("p");
    earlier.className = "muted";
    earlier.textContent = `Nothing new last time. ${dashRelativeTime(shown.finished_at || shown.started_at)}, it found:`;
    body.appendChild(earlier);
  }
  const kinds = document.createElement("ul");
  kinds.className = "night-kinds";
  for (const kind of Object.keys(counts).sort()) nightKindLine(kinds, shown.id, kind, counts[kind]);
  body.appendChild(kinds);
}
