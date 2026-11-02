// The capture card's second file (INBOX 1479 steps 3 and 4): the colour dots,
// the reminder bell, the tag suggestions, the pictures and Draw, fetched with
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

//: `pick`: the bar's picture button took the click that fetched this file, so
//: the file picker opens now (the click's permission to open it is still live).
async function mountCaptureExtras(pick = false) {
  const card = captureCard.root;
  if (!card.dataset.extras) {
    card.dataset.extras = "1";
    card.addEventListener("input", scheduleCaptureSuggestions);
    captureCardField("bell").append(captureBell());
    mountCapturePictures(card);
  }
  if (pick) captureCardField("file").click();
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

// --- Pictures and Draw ---------------------------------------------------------------

//: A note carries a handful of pictures, not an album.
const CAPTURE_PICTURE_LIMIT = 8;

//: The picture button and the Draw segment in the foot, the hidden picker, and
//: the strip of thumbnails under the words. A paste of an image is a picture too.
function mountCapturePictures(card) {
  const seg = card.querySelector(".capture-card-modes");
  const draw = captureCardEl("button", "", { type: "button", "data-cc": "draw", "aria-haspopup": "dialog", title: "Draw a picture for this note" });
  draw.textContent = "Draw";
  const picture = captureCardButton("ghost small icon-only", "Add pictures", "ph-image", "picture");
  const file = captureCardEl("input", "hidden", { type: "file", accept: "image/*", multiple: "", tabindex: "-1", "aria-hidden": "true", "aria-label": "Choose pictures for this note", "data-cc": "file" });
  seg.append(draw);
  seg.after(picture, file);
  card.querySelector(".note-composer").after(captureCardEl("div", "capture-card-thumbs", { "data-cc": "thumbs", hidden: "" }));
  draw.addEventListener("click", openCaptureDraw);
  picture.addEventListener("click", () => file.click());
  file.addEventListener("change", () => {
    addCapturePictures([...file.files]);
    file.value = "";
  });
  card.addEventListener("paste", (event) => {
    const images = [...(event.clipboardData?.files || [])].filter((item) => item.type.startsWith("image/"));
    if (!images.length) return;
    event.preventDefault();
    addCapturePictures(images);
  });
}

//: Images only, up to the limit; what was left out is said under the card.
function addCapturePictures(files, alt = "") {
  const images = files.filter((file) => file.type.startsWith("image/"));
  const room = CAPTURE_PICTURE_LIMIT - captureCard.pictures.length;
  for (const file of images.slice(0, Math.max(room, 0))) {
    captureCard.pictures.push({ file, preview: URL.createObjectURL(file), alt: alt || file.name.replace(/\.[^.]+$/, ""), uploaded: "" });
  }
  renderCaptureThumbs();
  const left = files.length - Math.min(images.length, Math.max(room, 0));
  captureCardStatus(left ? `Added what fits: a note takes ${CAPTURE_PICTURE_LIMIT} pictures, and only pictures.` : "", Boolean(left));
}

function renderCaptureThumbs() {
  const box = captureCardField("thumbs");
  if (!box) return;
  box.replaceChildren(...captureCard.pictures.map(captureThumb));
  box.hidden = !captureCard.pictures.length;
}

function captureThumb(picture) {
  const item = captureCardEl("span", "capture-card-thumb");
  const image = captureCardEl("img", "", { src: picture.preview, alt: picture.alt });
  const remove = captureCardButton("ghost small icon-only", `Remove ${picture.alt}`, "ph-x", "thumb-remove");
  remove.addEventListener("click", () => removeCapturePicture(picture));
  item.append(image, remove);
  return item;
}

function removeCapturePicture(picture) {
  URL.revokeObjectURL(picture.preview);
  captureCard.pictures = captureCard.pictures.filter((item) => item !== picture);
  renderCaptureThumbs();
}

//: The editor's own path: each picture goes to /media/upload and the note
//: refers to it as markdown. One already sent (a retry after a failure) is not
//: sent twice. Returns the markdown lines, one picture a paragraph.
async function uploadCapturePictures() {
  const lines = [];
  for (const picture of captureCard.pictures) {
    if (!picture.uploaded) {
      const form = new FormData();
      form.append("file", picture.file, picture.file.name);
      const sent = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form });
      if (!sent?.url) throw new Error("Couldn't upload a picture. Nothing was saved.");
      picture.uploaded = sent.url;
    }
    lines.push(`![${picture.alt}](${picture.uploaded})`);
  }
  return lines.join("\n\n");
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
  addCapturePictures([new File([blob], `sketch-${stamp}.png`, { type: "image/png" })], caption);
}
