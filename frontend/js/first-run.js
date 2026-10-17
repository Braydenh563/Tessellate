// first-run.js: the dashboard's first steps (WORLD_CLASS_PLAN 25c, Brief 49).
// Three steps a new notebook is walked through, each ticked when it is done
// rather than when it is pressed: your name, a first note, a first answer from
// your notes (which needs no model). Beside them, once, the sample notebook:
// a handful of example notes to explore, taken away again in one press
// (`POST` and `DELETE /help/sample-notebook`). The card stays on the dashboard
// until the three are done and the sample notes are gone, or until Hide; it
// was the empty notebook's card only, so it went with the first note, before
// the step that shows what the notes are for. Lazy: dashboard.js's
// `renderFirstStepsLazy` fetches it while the steps may still be shown.

async function firstStepsState() {
  const named = Boolean(((typeof prefsCache === "object" && prefsCache?.display_name) || "").trim());
  //: An answer from Ask is kept in the Ask history, a chat in the chat list:
  //: either one is the third step done.
  const [asks, chats, sample] = await Promise.all([
    apiJson("/ask-history/stats").catch(() => ({ total: 0 })),
    apiJson("/conversations?limit=1").catch(() => []),
    apiJson("/help/sample-notebook").catch(() => ({ live: 0, added: true })),
  ]);
  const samples = sample.live || 0;
  const noted = allEntries.length > samples;
  const asked = (asks.total || 0) > 0 || (Array.isArray(chats) && chats.length > 0);
  return { named, noted, asked, samples, offered: Boolean(sample.added) };
}

function firstStepButton({ number, done, icon, label, note, doneNote, run }) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "start-step";
  button.classList.toggle("is-done", done);
  const glyph = document.createElement("span");
  glyph.className = "start-step-icon";
  glyph.setAttribute("aria-hidden", "true");
  setLabel(glyph, done ? "ph:check-circle" : icon);
  const text = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = `${number}. ${label}`;
  const line = document.createElement("span");
  line.className = "muted";
  line.textContent = done ? doneNote : note;
  text.append(title, line);
  button.append(glyph, text);
  //: No `aria-label` when done: its note starts "Done.", and a name that is not
  //: the visible words fails WCAG 2.5.3 (axe label-content-name-mismatch).
  button.addEventListener("click", run);
  return button;
}

//: Step one is typed where it is asked: a name field in the tile, Enter
//: saves it (`PUT /preferences`), rather than a door into Settings, General,
//: whose Save button is three presses further on.
function firstStepName(host) {
  const form = document.createElement("form");
  form.className = "start-step start-step-form";
  const glyph = document.createElement("span");
  glyph.className = "start-step-icon";
  glyph.setAttribute("aria-hidden", "true");
  setLabel(glyph, "ph:hand-waving");
  const text = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = "1. Your name";
  const input = document.createElement("input");
  input.type = "text";
  input.id = "first-steps-name";
  input.maxLength = 60;
  input.autocomplete = "given-name";
  input.placeholder = "Your first name, then Enter";
  input.setAttribute("aria-label", "Your name, for the greeting and Atlas");
  text.append(title, input);
  form.append(glyph, text);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = input.value.trim();
    if (!name) return;
    try {
      prefsCache = await apiJson("/preferences", { method: "PUT", body: JSON.stringify({ display_name: name }) });
    } catch (err) {
      toast(`Your name could not be saved: ${err.message}`, true);
      return;
    }
    renderDashboardGreeting();
    renderFirstSteps(host);
  });
  return form;
}

async function firstStepsSample(host, add, event) {
  //: Eight saves, each indexed for search: seconds on a first launch, so the
  //: press says it is working and cannot be pressed twice.
  const button = event?.currentTarget;
  if (button) {
    setBusy(button, true, add ? "Adding the sample notes" : "Removing the sample notes");
  }
  let ids = [];
  try {
    if (add) {
      const made = await apiJson("/help/sample-notebook", { method: "POST" });
      ids = made.ids || [];
      toast(`Added ${made.created} sample notes. Try asking "where is the spare key?"`);
    } else {
      const gone = await apiJson("/help/sample-notebook", { method: "DELETE" });
      ids = gone.ids || [];
      //: In the bin, so the bin's Restore is the undo (rule 1.9: no new undo).
      toast(`Moved ${gone.binned} sample notes to the bin.`);
    }
  } catch (err) {
    toast(`The sample notes could not be ${add ? "added" : "removed"}: ${err.message}`, true);
    renderFirstSteps(host);
    return;
  }
  //: The eight notes it touched, and the categories it made or emptied.
  await Promise.all([refreshEntries(ids), loadCategories()]);
  renderFirstSteps(host);
}

//: A worded button named by its words (WCAG 2.5.3): `smallButton` names every
//: button by its title, which suits an icon and hides a label.
function firstStepsDoor(label, title, run) {
  const button = smallButton(label, title, run);
  button.removeAttribute("aria-label");
  return button;
}

function firstStepsHide(host) {
  prefs.set("firstStepsHidden", "1");
  host.replaceChildren();
}

function firstStepsCard(host, state) {
  const card = document.createElement("section");
  card.className = "card dash-widget dash-getting-started first-steps";
  card.setAttribute("aria-labelledby", "first-steps-title");
  const title = document.createElement("h2");
  title.id = "first-steps-title";
  //: Not "Your notebook is empty" again: the hero says so (INBOX 472).
  title.textContent = "Start in three steps";
  const blurb = document.createElement("p");
  blurb.className = "muted";
  blurb.textContent =
    "Type a thought and it is filed for you; ask a question and the answer comes from your notes. " +
    "Everything stays on this machine, and none of it needs an AI model.";
  const steps = document.createElement("div");
  steps.className = "start-steps";
  steps.append(
    state.named
      ? firstStepButton({
          number: 1, done: true, icon: "ph:hand-waving", label: "Your name",
          doneNote: "Done. Change it in Settings, General.",
          run: () => openSettingsModal("preferences"),
        })
      : firstStepName(host),
    firstStepButton({
      number: 2, done: state.noted, icon: "ph:pencil-simple", label: "Write a note",
      note: "A half sentence is fine; add a #tag if you like.", doneNote: "Done. Write another any time.",
      run: () => startNewNote(),
    }),
    firstStepButton({
      number: 3, done: state.asked, icon: "ph:chat-circle", label: "Ask your notebook",
      note: "An answer from your notes, no AI model needed.", doneNote: "Done. Ask again from Notes, Ask.",
      run: () => openAskFromDashboard(),
    })
  );
  const more = document.createElement("div");
  more.className = "row wrap first-steps-more";
  //: Offered once: on a notebook with no notes of its own, until it is taken.
  if (state.samples) {
    more.appendChild(
      firstStepsDoor("ph:trash Remove the sample notes", "Move the sample notes to the bin", (event) => firstStepsSample(host, false, event))
    );
  } else if (!state.noted && !state.offered) {
    more.appendChild(
      firstStepsDoor("ph:books Try a sample notebook", "Add eight example notes to explore; remove them in one press", (event) => firstStepsSample(host, true, event))
    );
  }
  more.append(
    firstStepsDoor("ph:backpack Bring notes in", "Import from a file or another app", () => openSettingsModal("data")),
    firstStepsDoor("ph:compass Take the tour", "Two minutes through what is here", () => openTour("basics")),
    firstStepsDoor("ph:book-open-text Read the manual", "Every help topic on one page", () => lazyScript("/js/manual.js").then((ok) => ok && openManual()))
  );
  //: Hide is offered once there is a notebook to show instead.
  if (state.noted || state.samples) more.appendChild(firstStepsDoor("ph:eye-slash Hide these steps", "Hide the first steps for good", () => firstStepsHide(host)));
  card.append(title, blurb, steps, more);
  return card;
}

async function renderFirstSteps(host, cardOff = false) {
  renderGetStarted();
  if (cardOff) return void host.replaceChildren();
  lazyScript("/css/first-run-lazy.css");
  const state = await firstStepsState();
  //: All three done and no sample notes left: the steps have done their job.
  if (state.named && state.noted && state.asked && !state.samples) {
    prefs.set("firstStepsHidden", "1");
    host.replaceChildren();
    return;
  }
  host.replaceChildren(firstStepsCard(host, state));
  //: The greeting's "Add your name" is step one's second door: one is enough.
  document.getElementById("dash-name-nudge")?.remove();
}

//: **The steps stay reachable** (INBOX 904 B01: a setup popup was closed by
//: accident and there was no way back). The card above hides itself once
//: there are notes or Hide is pressed; these two doors never do: the
//: dashboard's "Get started" menu (`renderGetStarted`, below) and the
//: same checklist as the first row of the notifications panel
//: (`firstStepsBellRow`, called from `openNotifications`). Both are built
//: from the steps below, so a step is worded once.
function getStartedSteps(state) {
  return [
    {
      done: state.named, label: "Add your name",
      note: "For the greeting and Atlas.", doneNote: "Done. Change it in Settings, General.",
      run: () => openSettingsModal("preferences"),
    },
    {
      done: state.noted, label: "Write a note",
      note: "A half sentence is fine; add a #tag if you like.", doneNote: "Done. Write another any time.",
      run: () => startNewNote(),
    },
    {
      done: state.asked, label: "Ask your notebook",
      note: "An answer from your notes, no AI model needed.", doneNote: "Done. Ask again from Notes, Ask.",
      run: () => openAskFromDashboard(),
    },
  ];
}

function getStartedItems(state) {
  const items = getStartedSteps(state).map((step) => ({
    label: `${step.done ? "ph:check-circle" : "ph:circle"} ${step.label}${step.done ? " · done" : ""}`,
    title: step.done ? step.doneNote : step.note,
    group: "steps",
    run: step.run,
  }));
  items.push(
    { label: "ph:compass Take the tour", title: "Two minutes through what is here", group: "more", run: () => openTour("basics") },
    { label: "ph:hand-waving Replay the welcome", title: "The first screen a new notebook shows", group: "more", run: () => openOnboarding() },
    { label: "ph:book-open-text Read the manual", title: "Every help topic on one page", group: "more", run: () => lazyScript("/js/manual.js").then((ok) => ok && openManual()) }
  );
  return items;
}

//: A row for the notifications panel while a step is left; none once all three
//: are done (the dashboard's menu still lists them, ticked).
async function firstStepsBellRow() {
  lazyScript("/css/first-run-lazy.css");
  const steps = getStartedSteps(await firstStepsState());
  const left = steps.filter((step) => !step.done).length;
  if (!left) return null;
  const row = document.createElement("li");
  row.className = "notif-row notif-start";
  const icon = document.createElement("span");
  icon.className = "notif-icon";
  setLabel(icon, "ph:list-checks");
  icon.setAttribute("aria-hidden", "true");
  const body = document.createElement("div");
  body.className = "notif-body";
  const title = document.createElement("strong");
  title.className = "notif-title";
  title.textContent = `Get started, ${steps.length - left} of ${steps.length} done`;
  const list = document.createElement("ul");
  list.className = "notif-start-steps";
  for (const step of steps) {
    const item = document.createElement("li");
    const button = smallButton(`${step.done ? "ph:check-circle" : "ph:circle"} ${step.label}`, step.done ? step.doneNote : step.note, () => {
      closeNotifications();
      step.run();
    });
    button.removeAttribute("aria-label");
    button.classList.add("quiet", "notif-start-step");
    button.classList.toggle("is-done", step.done);
    item.appendChild(button);
    list.appendChild(item);
  }
  body.append(title, list);
  row.append(icon, body);
  return row;
}

//: **Get started, the menu** (INBOX 904 B01): the same steps ticked, in the
//: dock beside Customise, whatever the card did. Built once first-run.js and
//: the three ticks have arrived, so the dock gains it a moment after the page.
async function renderGetStarted() {
  const slot = $("dash-start");
  if (!slot) return;
  const state = await firstStepsState().catch(() => null);
  if (!state) return;
  const menu = kebabMenu(getStartedItems(state), "Get started: the first steps");
  const opener = menu.querySelector("button");
  setLabel(opener, "ph:list-checks");
  opener.querySelector("i")?.classList.add("ph-lead");
  const word = document.createElement("span");
  word.className = "dock-word";
  word.textContent = "Get started";
  opener.append(word);
  opener.classList.remove("icon-only");
  opener.classList.add("ghost");
  opener.id = "dash-start-menu";
  slot.replaceChildren(menu);
}
