// The capture card's second file (INBOX 1479 steps 3 and 4): the colour dots,
// the reminder bell, the tag suggestions and Draw, fetched with
// the card by capture-card.js. Everything here is optional to a save: the card keeps the
// chosen colour (`captureCard.colour`) and time (`captureCard.due`) and the
// core sends them.

//: The dots the card offers: eight of the twelve swatches the category picker
//: draws (`CATEGORY_PALETTE`, notes-list.js), by key, so the theme gives the shade.
const CAPTURE_COLOURS = ["red", "orange", "amber", "green", "teal", "blue", "violet", "pink"];

//: The reminder setter's own quick-set times (`presetDate`, shell-reminders.js).
const CAPTURE_REMINDERS = [
  ["30m", "In 30 min", "soon"], ["1h", "In 1 hour", "soon"], ["3h", "In 3 hours", "soon"],
  ["tonight", "Tonight 7pm", "day"], ["tomorrow", "Tomorrow 9am", "day"], ["tomorrowpm", "Tomorrow 2pm", "day"],
  ["weekend", "This weekend", "later"], ["nextweek", "Next week", "later"],
];

async function mountCaptureExtras() {
  const card = captureCard.root;
  if (!card.dataset.extras) {
    card.dataset.extras = "1";
    card.addEventListener("input", scheduleCaptureSuggestions);
    captureCardField("bell").append(captureBell());
    captureCard.mountLock();
    mountCaptureDraw(card);
  }
  await syncCaptureExtras();
}

//: Repaints what the draft says: the dot that is on, the bell's time.
async function syncCaptureExtras() {
  await ensureModule("categories");
  const holder = captureCardField("colours");
  const palette = Object.fromEntries(CAPTURE_COLOURS.map((key) => [key, CATEGORY_PALETTE[key]]));
  holder.replaceChildren(
    swatchPicker({
      label: "Note colour",
      value: captureCard.colour,
      palette,
      none: "None",
      onChoose: (key) => {
        captureCard.colour = key;
        keepCaptureDraft();
      },
    }),
  );
  paintCaptureBell();
  captureCard.settle();
}

function captureBell() {
  const items = CAPTURE_REMINDERS.map(([key, label, group]) => ({
    label: `ph:clock ${label}`,
    group,
    run: () => setCaptureReminder(presetDate(key)),
  }));
  items.push({ label: "ph:bell-slash No reminder", group: "none", run: () => setCaptureReminder(null) });
  const wrap = labelledMenu("ph:bell", items, "Remind me about this note", "ghost small icon-only capture-card-bell-btn");
  const readout = document.createElement("span");
  readout.className = "muted text-sm capture-card-due";
  readout.dataset.cc = "due";
  wrap.append(readout);
  return wrap;
}

function setCaptureReminder(date) {
  captureCard.due = date ? date.toISOString() : null;
  paintCaptureBell();
  keepCaptureDraft();
}

function paintCaptureBell() {
  const due = captureCardField("due");
  const button = captureCard.root.querySelector(".capture-card-bell-btn");
  if (!due || !button) return;
  const said = captureCard.due ? `Reminder ${relativeWhen(captureCard.due)}` : "";
  due.textContent = said;
  setLabel(button, captureCard.due ? "ph:bell-ringing" : "ph:bell");
  button.setAttribute("aria-label", said ? `Remind me about this note. ${said}` : "Remind me about this note");
}

// --- Tag suggestions while writing (the Capture sub-tab's own engine) ---------

function scheduleCaptureSuggestions() {
  clearTimeout(captureCard.suggestTimer);
  const draft = captureCardDraft();
  const text = draft.mode === "todo" ? captureItemsToLines(draft.items) : draft.body.trim();
  if (text.length < 20) return clearCaptureSuggestions();
  captureCard.suggestTimer = setTimeout(() => askCaptureSuggestions(text, draft), 1200);
}

function clearCaptureSuggestions() {
  captureCard.suggestSeq++;
  const row = captureCardField("suggest");
  row.replaceChildren();
  row.classList.add("hidden");
}

async function askCaptureSuggestions(text, draft) {
  const seq = ++captureCard.suggestSeq;
  const body = JSON.stringify({ content: text, tags: captureTagList(draft.tags), title: draft.title });
  const result = await apiJson("/entries/suggest-tags", { method: "POST", body, silent: true }).catch(() => ({}));
  if (seq !== captureCard.suggestSeq || captureCard.root.hidden) return;
  renderCaptureSuggestions(result.suggested_tags || [], result.suggested_tag_reasons);
}

function renderCaptureSuggestions(tags, reasons) {
  const row = captureCardField("suggest");
  row.replaceChildren();
  row.classList.toggle("hidden", !tags.length);
  captureCard.settle();
  if (!tags.length) return;
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = "Suggested:";
  row.append(label);
  for (const tag of tags) {
    const pick = chip(`ph:plus ${tag}`, "tag", () => {
      const field = captureCardField("tags");
      field.value = `${field.value.trim()} #${tag}`.trim();
      field.dispatchEvent(new Event("input", { bubbles: true }));
      pick.remove();
      if (!row.querySelector(".chip")) row.classList.add("hidden");
    });
    pick.title = reasons?.[tag] || `Add the "${tag}" tag`;
    row.append(pick);
  }
}

// --- Draw ---------------------------------------------------------------------------

//: The Draw segment in the foot. The pictures and files it adds to are the card's
//: staging (capture-stage.js), which the desk's window has too; Draw is the app's alone.
function mountCaptureDraw(card) {
  const draw = captureCardEl("button", "", { type: "button", "data-cc": "draw", "aria-haspopup": "dialog", title: "Draw a picture for this note" });
  draw.textContent = "Draw";
  card.querySelector(".capture-card-modes").append(draw);
  draw.addEventListener("click", openCaptureDraw);
}

//: Draw: the app's sketch pad in its overlay, saving into this card instead of
//: filing a note of its own.
function captureSketchHost() {
  captureCard.sketchHost ||= {
    ...sketchHost(),
    title: "Draw for this note",
    saveLabel: "Add to note",
    saveTitle: "Add this drawing to the note",
    captionHint: "Caption (optional)",
    save: addCaptureSketch,
  };
  return captureCard.sketchHost;
}

function openCaptureDraw() {
  return openSketch({ host: captureSketchHost() });
}

async function addCaptureSketch(blob, caption) {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  addCaptureFiles([new File([blob], `sketch-${stamp}.png`, { type: "image/png" })], caption);
}
