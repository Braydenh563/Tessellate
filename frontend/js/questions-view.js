// questions-view.js: Notes, Questions (WORLD_CLASS_PLAN I3, row 7), the
// questions your notes ask, over `GET /questions`, with Open, Answered and
// Dropped, the night pass's Read notes now, and "Ask about these".
//
// Lazy (app.js `LAZY_MODULES.questionsView`), moved out of capture-ask.js on
// 2026-10-06 (INBOX 688) to keep the boot scripts under their gzip total:
// nothing here runs until the Questions sub-tab is shown, which calls
// `initQuestionsView` and `loadQuestions` through their stand-ins
// (`LAZY_ENTRY_POINTS`). The Ask scope variable (`askScope`) stays in
// capture-ask.js, since `askQuestion` reads it; its setter, `setAskScope`, is
// at the end of this file, the only place that calls it.

const questionsView = { state: "open", offset: 0, ready: false, entry: null, last: null };

function questionWhen(iso) {
  const when = iso ? new Date(iso) : null;
  return when && !Number.isNaN(when.getTime()) ? when.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
}

function questionButton(icon, label, onClick) {
  const button = smallButton(icon, label, onClick);
  button.setAttribute("aria-label", label);
  return button;
}

function questionRow(item) {
  const li = evidenceSpan("night-fact question-row", "", "li");
  const text = evidenceSpan("dash-list-text");
  //: The words without their markdown (`display`, INBOX 745 (b)); the note
  //: is the group's heading above, so the line under says only when.
  text.append(evidenceSpan("dash-list-title night-fact-text", item.display || item.text), evidenceSpan("dash-list-preview", ["Asked", questionWhen(item.asked_at)].filter(Boolean).join(" ")));
  const by = item.answered_by;
  if (item.state === "answered" && by) {
    //: The answered-by link (I3, decided 2026-10-04): the answering sentence,
    //: opening its note; a title that starts the quote is not said twice.
    const stem = String(by.note_title || "").replace(/…$/, "");
    const named = by.note_title && !(by.text && by.text.startsWith(stem)) ? ` in “${by.note_title}”` : "";
    const answer = document.createElement("button");
    answer.type = "button";
    answer.className = "ghost small question-answer-link";
    answer.title = "Open the note that answers it";
    answer.addEventListener("click", () => flashEntry(by.entry_id));
    answer.textContent = ["Answered", questionWhen(by.at)].filter(Boolean).join(" ") + named + (by.text ? `: “${by.text}”` : "");
    text.append(answer);
  }
  const actions = evidenceSpan("night-fact-actions");
  const send = (state, entry_id = null) =>
    apiJson(`/questions/${item.id}`, { method: "POST", body: JSON.stringify({ state, entry_id }) });
  const move = (state, entry_id = null) => {
    const was = item.state;
    return send(state, entry_id)
      .then(() => {
        pushUndo(`Marked a question ${state}`, () => send(was).then(() => loadQuestions()), () => send(state, entry_id).then(() => loadQuestions()));
        return loadQuestions();
      })
      .catch((error) => toast(error.message || "Couldn't change that question.", true));
  };
  actions.append(questionButton("ph:arrow-square-out", "Open the note that asks it", () => flashEntry(item.entry_id)));
  if (item.state === "open") {
    actions.append(
      questionButton("ph:check-circle", "Mark answered: choose the note that answers it", async () => {
        const entry = await pickEntryDialog("Which note answers it?");
        if (entry) move("answered", entry.id);
      }),
      questionButton("ph:minus-circle", "Drop: it no longer matters", () => move("dropped"))
    );
  } else {
    actions.append(questionButton("ph:arrow-counter-clockwise", "Reopen", () => move("open")));
  }
  li.append(text, actions);
  return li;
}

//: Icon, title, sentence per state: the empty state recipe (`.empty-state`,
//: 02-chat-graph.css), as Recordings uses it. Open also gets the one action.
const QUESTIONS_EMPTY = {
  open: ["ph-question", "No open questions", "Read notes now finds the questions your notes ask."],
  answered: ["ph-check-circle", "Nothing answered yet", "When a later note answers a question, it moves here."],
  dropped: ["ph-minus-circle", "Nothing dropped", "A question you drop because it no longer matters is kept here."],
};

function questionsEmpty(state) {
  const [glyph, heading, sentence] = QUESTIONS_EMPTY[state];
  const li = document.createElement("li");
  li.className = "empty-state questions-empty";
  const icon = document.createElement("span");
  icon.className = "empty-icon";
  icon.setAttribute("aria-hidden", "true");
  const mark = document.createElement("i");
  mark.className = `ph ${glyph} ph-lead`;
  icon.appendChild(mark);
  const title = document.createElement("p");
  title.className = "empty-title";
  title.textContent = heading;
  const line = document.createElement("p");
  line.textContent = sentence;
  li.append(icon, title, line);
  if (state === "open") {
    const read = document.createElement("button");
    read.type = "button";
    read.className = "ghost small";
    const spin = document.createElement("i");
    spin.className = "ph ph-arrow-clockwise ph-lead";
    spin.setAttribute("aria-hidden", "true");
    read.append(spin, " Read notes now");
    read.addEventListener("click", () => $("questions-refresh").click());
    li.appendChild(read);
  }
  return li;
}

async function loadQuestions({ more = false } = {}) {
  const list = $("questions-list");
  if (!list) return;
  if (!more) questionsView.offset = 0;
  //: The newest load wins: the sub-tab's own load and a card's "kept to this
  //: note" one start together, and the slower answer drew last (measured:
  //: the unfiltered list replaced the filtered one).
  const seq = (questionsView.seq = (questionsView.seq || 0) + 1);
  let reply;
  try {
    const one = questionsView.entry ? `&entry_id=${questionsView.entry.id}` : "";
    reply = await apiJson(`/questions?state=${questionsView.state}&limit=30&offset=${questionsView.offset}${one}`, { silent: true });
  } catch {
    surfaceFailed(list, "your questions", () => loadQuestions());
    return;
  }
  if (seq !== questionsView.seq) return;
  if (!more) {
    list.replaceChildren();
    questionsView.last = null;
  }
  const items = reply.items || [];
  //: **Grouped by the note that asks them** (INBOX 745 (c)): the listing is
  //: note by note already, so a heading goes in where the note changes, the
  //: note's title as a button that opens it.
  for (const item of items) {
    if (item.entry_id !== questionsView.last) {
      questionsView.last = item.entry_id;
      const head = document.createElement("li");
      head.className = "question-group";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "question-group-link";
      open.title = "Open the note that asks these";
      setLabel(open, `ph:note ${item.note_title || "A note"}`);
      open.addEventListener("click", () => flashEntry(item.entry_id));
      head.append(open);
      list.appendChild(head);
    }
    list.appendChild(questionRow(item));
  }
  questionsView.offset += items.length;
  const counts = reply.counts || {};
  //: The counts ride on the select's rows (INBOX 665), "Answered (2)", and
  //: a state with none reads as its word alone.
  for (const option of $("questions-state").options) {
    const count = counts[option.value] || 0;
    const text = count ? `${option.dataset.label} (${count})` : option.dataset.label;
    if (option.textContent !== text) option.textContent = text;
  }
  $("questions-more").classList.toggle("hidden", questionsView.offset >= (reply.total || 0));
  const ask = $("questions-ask");
  ask.disabled = !counts.open;
  ask.title = counts.open ? "Ask about the questions you have not answered yet" : "No open questions to ask about";
  const lead = $("questions-lead");
  lead.replaceChildren();
  if (!reply.total && !questionsView.entry) list.appendChild(questionsEmpty(questionsView.state));
  //: Kept to one note (its card's count): said, with the way back to all.
  if (questionsView.entry) {
    const all = document.createElement("button");
    all.type = "button";
    all.className = "ghost small";
    setLabel(all, "ph:x Show every note's");
    all.addEventListener("click", () => questionsForNote(null));
    lead.replaceChildren(`Only the questions in “${questionsView.entry.title}”. ${reply.total ? "" : "None here. "}`, all);
  }
}

//: Open the list kept to one note, or to every note again with null.
function questionsForNote(entryId) {
  initQuestionsView();
  const entry = entryId && allEntries.find((e) => e.id === entryId);
  questionsView.entry = entryId ? { id: entryId, title: entry ? clipText(notePreviewText(flattenNoteMarkdown(entry.title || entry.content || "")), 48) : "this note" } : null;
  questionsView.state = $("questions-state").value = "open";
  loadQuestions();
}

function initQuestionsView() {
  if (questionsView.ready || !$("questions")) return;
  questionsView.ready = true;
  const state = $("questions-state");
  state.value = questionsView.state;
  state.addEventListener("change", () => {
    questionsView.state = state.value;
    loadQuestions();
  });
  //: INBOX 551: the night pass, now (it runs unattended only with background
  //: tasks on, which is off by default), then the list.
  $("questions-refresh").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    setBusy(button, true, "Reading\u2026");
    const reply = await apiJson("/night/run", { method: "POST", body: JSON.stringify({ budget: 20000 }) }).catch(() => null);
    setBusy(button, false);
    if (reply?.paused) toast("Reading is paused in Settings, What it learned.", "info");
    loadQuestions();
  });
  $("questions-more").addEventListener("click", () => loadQuestions({ more: true }));
  $("questions-ask").addEventListener("click", () => {
    //: The Ask scope: the next answer reads the notes with open questions.
    setAskScope("questions");
    showNotesSection("ask");
    const box = $("question");
    if (!box.value.trim()) box.value = "What am I still undecided about?";
    box.focus();
  });
  $("ask-scope-clear")?.addEventListener("click", () => {
    setAskScope(null);
    $("question")?.focus();
  });
}

function setAskScope(scope) {
  askScope = scope || null;
  $("ask-scope")?.classList.toggle("hidden", !askScope);
}
