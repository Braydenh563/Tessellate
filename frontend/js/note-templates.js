// note-templates.js: the Capture box's template picker, its dialog of radio
// rows, preview and Use this template button. Moved out of app.js on
// 2026-10-05 (app.js's gzip cap, tests/test_static_compression.py): it opens
// only from the Templates button, so the boot never needs it. Loaded on first
// use by `LAZY_MODULES.noteTemplates` (app.js), whose stand-ins for
// `openNoteTemplateDialog` and `useNoteTemplate` fetch this file and call the
// real one. `noteTemplateListKeys` has no stand-in on purpose: it reads
// `event.currentTarget` and calls `preventDefault`, which an async stand-in
// would reach too late, so the opener binds it to the list itself, once.

//: Here since 2026-10-06 (the boot scripts' total cap): only this picker
//: and the Settings list read it, the list through the stand-in.
//: **Built-ins and the person's own, as one catalogue** (INBOX 409, "templates
//: cant be edited"). The persona shape: a saved template that carries a
//: built-in's name is that built-in's edit, kept in `custom_templates` beside
//: the templates that are wholly the person's, so the Built-in group shows
//: the edit's text under the shipped name, Yours shows only their own, and
//: removing the edit is the reset. Nothing else is stored, and the built-in's
//: original text never leaves this file. Both readers (the Capture dropdown
//: and the Settings list) draw from this one function, so they cannot
//: disagree about which templates exist.
function templateCatalogue() {
  const saved = (prefsCache && prefsCache.custom_templates) || [];
  const edits = new Map(saved.map((t) => [t.name, t]));
  const builtin = BUILTIN_TEMPLATES.map((t) => {
    const edit = edits.get(t.name);
    return { ...(edit || t), builtin: true, overridden: Boolean(edit) };
  });
  const shipped = new Set(BUILTIN_TEMPLATES.map((t) => t.name));
  const custom = saved
    .filter((t) => !shipped.has(t.name))
    .map((t) => ({ ...t, builtin: false, overridden: false }));
  return { builtin, custom };
}

// --- the Capture box's template picker (INBOX 410) ---------------------------
//
// **Choosing is not making**, for notes as for documents. The owner decided it
// on 2026-09-24: the Capture box's templates get the confirm step the
// documents' New from a template has (`openDocTemplateDialog` in documents.js).
// The picker was a native `<select>` whose `change` filled the box the moment
// a name was touched, so arrowing down the list to read the names wrote the
// note once per name, and a template picked by mistake asked "replace what
// you've written?" before you had seen what it was. Now it is DESIGN.md's
// recipe for a dialog of choices that each make something: radio rows (yours
// first, then the built-in ones), the chosen row's text beside them, and one
// filled button, Use this template, that fills the box. Enter on the list and a
// double click also make it; the first row is chosen on open so one Enter still
// works. This file, not documents.js, because the Capture box is always loaded
// and the documents bundle is not.
const noteTemplateState = { choice: null, made: false };

//: The text a template puts in the Capture box. One function for the preview
//: and the fill, so the preview cannot show something the button would not
//: write (the recipe's rule, `docTemplateFill`'s for documents).
function noteTemplateFill(template) {
  return noteTemplateText(noteTemplateState.vars(template?.content, new Date(), template?.name)).replaceAll(NOTE_TEMPLATE_CURSOR, "");
}

//: The twin of `ai/template_fill.fill` (CHAT_PLAN X13): {weekday}, {week},
//: {title} and {n} written out by rule. {date} stays with `noteTemplateText`
//: (the person's own date format); any other {slot} is left in the text for
//: the person to fill, as `ai/template_fill.slots` names them.
Object.assign(noteTemplateState, {
  slot: /\{(\w+)\}/g,
  known: ["date", "weekday", "week", "title", "n", "time", "cursor", "clipboard"],
  //: ISO 8601 week number, the one `datetime.isocalendar()` gives.
  week(now) {
    const day = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    day.setUTCDate(day.getUTCDate() + 4 - (day.getUTCDay() || 7));
    return Math.ceil(((day - Date.UTC(day.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7);
  },
  vars(raw, now, title = "", n = 1) {
    const values = {
      weekday: now.toLocaleDateString("en-GB", { weekday: "long" }),
      week: String(this.week(now)),
      title: String(title || ""),
      n: String(n),
    };
    return String(raw || "").replace(this.slot, (whole, name) => (name in values ? values[name] : whole));
  },
  slots(raw) {
    const found = [...String(raw || "").matchAll(this.slot)].map((m) => m[1]);
    return [...new Set(found)].filter((name) => !this.known.includes(name));
  },
});

//: Yours first, then the built-in ones, as the old dropdown's groups were:
//: one recognisable shape for "your stuff first, then what shipped".
function noteTemplateRows() {
  const { builtin, custom } = templateCatalogue();
  return [...custom, ...builtin];
}

function chooseNoteTemplate(template, { focus = false } = {}) {
  if (!template) return;
  noteTemplateState.choice = template;
  for (const row of document.querySelectorAll("#note-template-list .doc-template-choice")) {
    const on = row.dataset.template === template.name;
    row.setAttribute("aria-checked", String(on));
    //: The radio pattern's roving tab stop, as in the documents' dialog.
    row.tabIndex = on ? 0 : -1;
    if (on && focus) row.focus();
  }
  showNoteTemplatePreview(template);
}

//: The chosen template's text as it will land in the box, inert and hidden
//: from a screen reader (each row already says what it is). A note is plain
//: text in the box, so the preview is the text itself, wrapped as it would be.
function showNoteTemplatePreview(template) {
  const pane = $("note-template-preview");
  if (!pane || !template) return;
  const page = document.createElement("div");
  page.className = "doc-template-page note-template-page";
  const text = document.createElement("p");
  text.className = "note-template-text";
  text.textContent = noteTemplateFill(template);
  page.appendChild(text);
  pane.replaceChildren(page);
}

async function useNoteTemplate() {
  //: A double click is a click and then a dblclick, and Enter can follow
  //: either: one fill per opening, whichever way it was confirmed.
  if (noteTemplateState.made || !noteTemplateState.choice) return;
  noteTemplateState.made = true;
  const template = noteTemplateState.choice;
  $("note-template-dialog")?.close();
  const box = $("entry-content");
  if (!box) return;
  //: Never silently overwrite what has already been typed: asked after the
  //: choice is confirmed, so the question names a template the writer has
  //: seen rather than one the list happened to land on.
  if (box.value.trim()) {
    const replace = await confirmDialog(
      `Replace what you've already written with the “${template.name}” template?`,
      { confirmLabel: "Replace", cancelLabel: "Keep my text" }
    );
    if (!replace) return;
  }
  const filled = await noteTemplateForUse({ ...template, content: noteTemplateState.vars(template.content, new Date(), template.name) });
  box.value = filled.text;
  box.dispatchEvent(new Event("input", { bubbles: true }));
  //: With no {{cursor}} mark, the first slot left to fill is selected, so typing replaces it.
  const slot = filled.caret < 0 ? noteTemplateState.slot.exec(filled.text) : null;
  noteTemplateState.slot.lastIndex = 0;
  const open = slot && !noteTemplateState.known.includes(slot[1]);
  placeTemplateCaret(box, open ? slot.index : filled.caret, open ? slot.index + slot[0].length : -1);
}

function noteTemplateListKeys(event) {
  const rows = [...event.currentTarget.querySelectorAll(".doc-template-choice")];
  if (!rows.length) return;
  const index = rows.findIndex((row) => row.getAttribute("aria-checked") === "true");
  const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
  let next = null;
  if (step) next = rows[(index + step + rows.length) % rows.length];
  else if (event.key === "Home") next = rows[0];
  else if (event.key === "End") next = rows[rows.length - 1];
  const find = (row) => noteTemplateRows().find((t) => t.name === row.dataset.template);
  if (next) {
    event.preventDefault();
    chooseNoteTemplate(find(next), { focus: true });
  } else if (event.key === "Enter") {
    //: Enter on a focused row would fire its click, which only chooses; on
    //: this list Enter is the confirmation, as it is on a form.
    event.preventDefault();
    useNoteTemplate();
  }
}

function openNoteTemplateDialog() {
  const dialog = $("note-template-dialog");
  const list = $("note-template-list");
  if (!dialog || !list) return;
  noteTemplateState.made = false;
  if (!list.dataset.keysBound) {
    list.addEventListener("keydown", noteTemplateListKeys);
    list.dataset.keysBound = "1";
  }
  const templates = noteTemplateRows();
  list.replaceChildren();
  for (const template of templates) {
    const li = document.createElement("li");
    li.setAttribute("role", "presentation");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost doc-template-choice";
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", "false");
    button.dataset.template = template.name;
    const name = document.createElement("strong");
    name.textContent = template.name;
    //: The row's one line: the template's own description when it has one,
    //: else which group it is in, so a row never repeats its preview.
    const hint = document.createElement("span");
    hint.className = "muted text-sm";
    //: A phrasing with slots of its own ("Log a workout: {what}") says what is left to fill.
    const slots = noteTemplateState.slots(template.content);
    hint.textContent = template.description || (slots.length ? `Fill in: ${slots.join(", ")}` : template.builtin ? (template.overridden ? "Built-in, edited" : "Built-in") : "Yours");
    const check = document.createElement("i");
    check.className = "ph ph-check doc-template-check";
    check.setAttribute("aria-hidden", "true");
    button.append(name, hint, check);
    button.addEventListener("click", () => chooseNoteTemplate(template));
    button.addEventListener("dblclick", useNoteTemplate);
    li.appendChild(button);
    list.appendChild(li);
  }
  dialog.showModal();
  chooseNoteTemplate(templates[0], { focus: true });
}

// Moved from capture-ask.js (boot gzip): every caller is in this file.
//: The caret at the template's `{{cursor}}`, in the editor when one is
//: mounted (it mirrors the textarea a frame later), else in the textarea;
//: at the end when the template has no mark.
function placeTemplateCaret(box, caret, end = -1) {
  requestAnimationFrame(() => {
    const at = caret >= 0 ? caret : box.value.length;
    const to = end >= at ? end : at;
    const surface = noteSurfaceIfAny(box);
    if (surface) {
      surface.focus();
      surface.setSelection?.(at, to);
    } else {
      box.focus();
      box.setSelectionRange(at, to);
    }
  });
}
