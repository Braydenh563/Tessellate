// goals-view.js: Notes, Goals (Brief 98), the goals and lists over `/goals`:
// a card each with its progress, its items ticked off in place, an add line
// and a menu (rename, target day, finish, delete with Undo).
//
// Lazy (app.js `LAZY_MODULES.goalsView`, with goals-lazy.css), like the
// Questions view: nothing here runs until the Goals sub-tab is shown, which
// hears `goals:show`, which `showNotesSection` fires after `ensureModule("goalsView")`. The agent's `edit_goals` tool writes the same rows.

(() => {
  const goalsView = { kind: "", state: "open", ready: false, seq: 0 };

  const EMPTY = {
    "": ["ph-target", "No goals or lists yet", "A goal has steps you tick off and a progress bar; a list is for shopping, packing or anything you cross off."],
    goal: ["ph-target", "No goals yet", "Add one, then break it into steps."],
    list: ["ph-list-checks", "No lists yet", "Add one, then add its lines."],
    done: ["ph-flag-checkered", "Nothing finished yet", "A goal you finish is kept here."],
  };

  async function send(path, method, body) {
    return apiJson(`/goals${path}`, { method, body: body === undefined ? undefined : JSON.stringify(body) });
  }

  function targetWords(iso) {
    const when = iso ? new Date(`${iso}T00:00:00`) : null;
    return when && !Number.isNaN(when.getTime()) ? when.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
  }

  //: Every change reloads the list: the server owns progress, and a tick elsewhere (Chat) shows here too.
  async function change(run, failed) {
    try {
      await run();
    } catch (error) {
      toast(error.message || voiceLine("failed", failed), true);
    }
    return loadGoals();
  }

  function goalMenu(goal) {
    const pct = goal.progress;
    return kebabMenu(
      [
        { label: "ph:pencil-simple Rename", run: async () => {
          const title = await promptDialog("Rename it", goal.title);
          if (title && title.trim() && title !== goal.title) await change(() => send(`/${goal.id}`, "PATCH", { title }), "rename that");
        } },
        ...(goal.kind === "goal" ? [{ label: "ph:calendar-blank Target day", title: "Year-month-day, or empty for none", run: async () => {
          const target = await promptDialog("Target day, as year-month-day (empty for none)", goal.target_date);
          if (target !== null && target !== undefined) await change(() => send(`/${goal.id}`, "PATCH", { target_date: target.trim() }), "set that day");
        } }] : []),
        goal.done_at
          ? { label: "ph:arrow-counter-clockwise Reopen", run: () => change(() => send(`/${goal.id}`, "PATCH", { done: false }), "reopen that") }
          : { label: "ph:flag-checkered Finish", title: pct.total && pct.done < pct.total ? `${pct.total - pct.done} left` : "", run: () => change(() => send(`/${goal.id}`, "PATCH", { done: true }), "finish that") },
        { label: `ph:trash Delete ${goal.kind}`, danger: true, run: () => removeGoal(goal) },
      ],
      `Menu for ${goal.title}`
    );
  }

  async function removeGoal(goal) {
    const gone = await send(`/${goal.id}`, "DELETE").catch((error) => {
      toast(error.message || voiceLine("failed", "delete that"), true);
      return null;
    });
    if (!gone) return;
    //: Undo makes it again (a new id), so Redo deletes that one.
    let current = null;
    const again = async () => {
      current = await send("", "POST", { title: gone.title, kind: gone.kind, target_date: gone.target_date, items: gone.items });
      await loadGoals();
    };
    const redo = async () => {
      if (current) await send(`/${current.id}`, "DELETE");
      await loadGoals();
    };
    offerUndo(`Deleted a ${gone.kind}`, `Deleted “${gone.title}”.`, again, redo);
    await loadGoals();
  }

  function itemRow(goal, item) {
    const li = document.createElement("li");
    li.className = "goal-item";
    li.dataset.item = item.id;
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = item.done;
    box.addEventListener("change", () => change(() => send(`/${goal.id}/items/${item.id}`, "PATCH", { done: box.checked }), "tick that"));
    label.append(box, evidenceSpan("goal-item-text", item.text));
    const drop = smallButton("ph:x", `Remove “${item.text}”`, () => change(() => send(`/${goal.id}/items/${item.id}`, "DELETE"), "remove that"));
    drop.classList.add("quiet");
    li.append(label, drop);
    return li;
  }

  function addLine(goal) {
    const form = document.createElement("form");
    form.className = "goal-add";
    const field = document.createElement("input");
    field.type = "text";
    field.maxLength = 300;
    field.placeholder = goal.kind === "goal" ? "Add a step" : "Add a line";
    field.setAttribute("aria-label", `Add to ${goal.title}`);
    form.append(field);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = field.value.trim();
      if (!text) return;
      field.value = "";
      change(() => send(`/${goal.id}/items`, "POST", { text }), "add that");
    });
    return form;
  }

  function goalCard(goal) {
    const li = document.createElement("li");
    li.className = "goal-card";
    li.dataset.goal = goal.id;
    const head = evidenceSpan("goal-head", "", "div");
    const icon = document.createElement("i");
    icon.className = `ph ${goal.kind === "goal" ? "ph-target" : "ph-list-checks"} ph-lead`;
    icon.setAttribute("aria-hidden", "true");
    const title = evidenceSpan("goal-title", goal.title, "h3");
    const { total, done, percent } = goal.progress;
    const facts = [total ? `${done} of ${total} done` : "No items yet", goal.target_date && `by ${targetWords(goal.target_date)}`, goal.done_at && "finished"].filter(Boolean).join(", ");
    head.append(icon, title, goalMenu(goal));
    const bar = document.createElement("progress");
    bar.className = "goal-bar";
    bar.max = 100;
    bar.value = percent;
    bar.setAttribute("aria-label", `${goal.title}: ${facts}`);
    const list = document.createElement("ul");
    list.className = "goal-items";
    for (const item of goal.items) list.appendChild(itemRow(goal, item));
    li.append(head, evidenceSpan("goal-facts muted", facts), bar, list, addLine(goal));
    return li;
  }

  function emptyState(key) {
    const [glyph, heading, sentence] = EMPTY[key] || EMPTY[""];
    const li = document.createElement("li");
    li.className = "empty-state goals-empty";
    const icon = evidenceSpan("empty-icon");
    icon.setAttribute("aria-hidden", "true");
    const mark = document.createElement("i");
    mark.className = `ph ${glyph} ph-lead`;
    icon.appendChild(mark);
    li.append(icon, evidenceSpan("empty-title", heading, "p"), evidenceSpan("", sentence, "p"));
    return li;
  }

  async function loadGoals() {
    const list = $("goals-list");
    if (!list) return;
    const seq = ++goalsView.seq;
    const finished = goalsView.state === "done";
    let reply;
    try {
      reply = await apiJson(`/goals?state=${goalsView.state}${goalsView.kind ? `&kind=${goalsView.kind}` : ""}`, { silent: true });
    } catch {
      surfaceFailed(list, "your goals", () => loadGoals());
      return;
    }
    if (seq !== goalsView.seq) return;
    //: The list is rebuilt, so the control the person was on (a tick box, an add line) is found again by its goal and item and refocused.
    const held = document.activeElement;
    const spot = held && list.contains(held) ? { goal: held.closest("[data-goal]")?.dataset.goal, item: held.closest("[data-item]")?.dataset.item, add: !!held.closest(".goal-add") } : null;
    list.replaceChildren(...reply.goals.map(goalCard));
    if (spot) {
      const card = list.querySelector(`[data-goal="${spot.goal}"]`);
      (spot.add ? card?.querySelector(".goal-add input") : card?.querySelector(`[data-item="${spot.item}"] input`))?.focus();
    }
    if (!reply.goals.length) list.appendChild(emptyState(finished ? "done" : goalsView.kind));
    const counts = reply.counts || {};
    for (const option of $("goals-show").options) {
      const count = option.value === "goal" || option.value === "list" ? counts[option.value] : option.value === "" ? (counts.goal || 0) + (counts.list || 0) : 0;
      const text = count ? `${option.dataset.label} (${count})` : option.dataset.label;
      if (option.textContent !== text) option.textContent = text;
    }
  }

  async function makeOne(kind) {
    const title = await promptDialog(kind === "goal" ? "Name the goal" : "Name the list", "", { confirmLabel: "Add" });
    if (!title || !title.trim()) return;
    await change(() => send("", "POST", { title: title.trim(), kind }), `add that ${kind}`);
    $("goals-list").querySelector(".goal-card .goal-add input")?.focus();
  }

  function initGoalsView() {
    if (goalsView.ready || !$("goals")) return;
    goalsView.ready = true;
    const show = $("goals-show");
    show.addEventListener("change", () => {
      goalsView.state = show.value === "done" ? "done" : "open";
      goalsView.kind = show.value === "goal" || show.value === "list" ? show.value : "";
      loadGoals();
    });
    $("goals-new-goal").addEventListener("click", () => makeOne("goal"));
    $("goals-new-list").addEventListener("click", () => makeOne("list"));
  }

  //: No global at all: `showNotesSection` loads this module (`ensureModule`) and then fires `goals:show`, each time the sub-tab is shown.
  document.addEventListener("goals:show", () => {
    initGoalsView();
    loadGoals();
  });
})();
