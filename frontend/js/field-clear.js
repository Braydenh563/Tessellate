// field-clear.js: a Clear control on the boxes people type into (INBOX 466,
// the owner: "a clear button on the note capture tab and in other main text
// areas where the user might want to quick clear their work").
//
// A lazy piece (app.js `LAZY_MODULES.fieldClear`, loaded a few seconds after
// boot, like quick-note.js: the boot scripts are at their gzip cap). The
// buttons are in index.html, `hidden`; this file shows each only while its box
// holds something, and wires the click: the words go, the toast offers Undo
// (`toastAction`, the app's one undo recipe) and Undo puts back the words, the
// title, the tags and the staged files, merging with anything typed since
// rather than overwriting it. Escape is not touched: it keeps what it did.
//
// A script writing a box (a send, "Ask about this") raises no `input` event,
// so each box's `value` setter is wrapped (`fieldClearWatchValue`); there is no
// poll. Capture's note is the exception: its setter is its own (documents.js
// `noteSurfaceOwnValue`, reinstalled whenever the editor mounts), so it is left
// alone. Its writers are covered anyway: a restored draft is in place before
// the wire-time sync, and a save clears it with the buttons (both measured).

(() => {
  const FIELD_CLEARS = [
    //: The title and the note each clear on their own (INBOX 1567): one undo step apiece, and the toast says which.
    {
      button: "capture-clear-title",
      fields: ["entry-title"],
      inline: "Clear the title",
      surface: "notes",
      said: "Cleared the title.",
      undoLabel: "Cleared the title",
    },
    {
      button: "capture-clear-body",
      fields: ["entry-content"],
      inline: "Clear the note",
      surface: "notes",
      said: "Cleared the note.",
      undoLabel: "Cleared the note",
      //: Ends where Clear all ends (the third row): in the box, the tag suggestions drawn from the old words gone.
      after: () => FIELD_CLEARS[2].after(),
    },
    {
      button: "capture-clear",
      fields: ["entry-content", "entry-title", "entry-tags"],
      surface: "notes",
      said: "Cleared everything.",
      undoLabel: "Cleared the note box",
      //: Files staged for Save go with the words, and come back with them.
      held: () => (typeof captureStagedFiles !== "undefined" ? captureStagedFiles.length : 0),
      take() {
        const files = captureStagedFiles;
        captureStagedFiles = [];
        renderCaptureFiles();
        return files;
      },
      put(files) {
        captureStagedFiles = [...files, ...captureStagedFiles];
        renderCaptureFiles();
      },
      after() {
        clearCaptureTagSuggestions();
        if (typeof focusCaptureBox === "function") focusCaptureBox();
      },
    },
    //: A modal dialog or overlay is drawn above the toasts, so its Undo is on its own status line.
    { button: "quick-note-clear", fields: ["quick-note-text"], status: "quick-note-status", surface: "quickNote" },
    { button: "ask-clear", fields: ["question"], surface: "notes" },
    { button: "chat-clear", fields: ["chat-input"], surface: "chat" },
    { button: "command-palette-clear", fields: ["command-palette-input"], status: "command-palette-status", surface: "palette" },
  ];

  function fieldClearBoxes(spec) {
    return spec.fields.map((id) => document.getElementById(id)).filter(Boolean);
  }

  function fieldClearSync(spec) {
    const button = document.getElementById(spec.button);
    if (!button) return;
    const full = fieldClearBoxes(spec).some((box) => box.value.trim()) || (spec.held ? spec.held() > 0 : false);
    //: Only on a change: a forced `toggle` rewrites the class attribute on every key (B59).
    if (button.classList.contains("hidden") === full) button.classList.toggle("hidden", !full);
  }

  //: Sets a box and tells the page it changed, so the counter, the draft kept
  //: in storage, the tag suggestions and the box's height all follow.
  function fieldClearWrite(box, value) {
    box.value = value;
    box.dispatchEvent(new Event("input", { bubbles: true }));
    if (typeof autoGrow === "function" && box.tagName === "TEXTAREA") autoGrow(box);
  }

  function fieldClearRun(spec) {
    const boxes = fieldClearBoxes(spec);
    const words = boxes.map((box) => box.value);
    const held = spec.take ? spec.take() : null;
    if (!words.some((w) => w.trim()) && !(held && held.length)) return;
    for (const box of boxes) fieldClearWrite(box, "");
    if (spec.after) spec.after();
    else boxes[0]?.focus();
    fieldClearSync(spec);
    const undo = () => {
      boxes.forEach((box, at) => {
        const typed = box.value.trim();
        const was = words[at];
        //: Typed since: the old words go in front, never over the new ones.
        fieldClearWrite(box, typed && was ? `${was}${box.tagName === "TEXTAREA" ? "\n\n" : " "}${box.value}` : was || box.value);
      });
      if (spec.put && held) spec.put(held);
      boxes[0]?.focus();
      fieldClearSync(spec);
    };
    const redo = () => {
      for (const box of boxes) fieldClearWrite(box, "");
      fieldClearSync(spec);
    };
    //: On the app's Undo stack too (INBOX 898), so Ctrl+Z brings the words back
    //: after the notice has gone and Ctrl+Shift+Z clears the box again.
    const step = pushUndo(spec.undoLabel || "Cleared a box", undo, redo);
    const line = spec.status && document.getElementById(spec.status);
    if (!line) return toastAction(spec.said || "Cleared.", "Undo", () => { settleUndoFromToast(step); undo(); });
    const undoButton = document.createElement("button");
    undoButton.type = "button";
    undoButton.className = "link-button";
    undoButton.textContent = "Undo";
    line.classList.remove("error");
    line.replaceChildren("Cleared. ", undoButton);
    const gone = () => line.replaceChildren();
    const timer = setTimeout(gone, 8000);
    undoButton.addEventListener("click", () => {
      clearTimeout(timer);
      gone();
      settleUndoFromToast(step);
      undo();
    });
    boxes[0].addEventListener("input", () => { clearTimeout(timer); gone(); }, { once: true });
  }

  //: **A value written by code moves the button too, without a poll** (audit
  //: 2026-10-05, FE-18). Code fills these boxes without an `input` event (a
  //: draft loaded into Capture, "Ask about this" filling the question), so the
  //: X used to be re-synced by a one-second interval for the whole session.
  //: Each box's own `value` setter is wrapped instead: the native setter runs,
  //: then the button is synced, once, in a microtask.
  function fieldClearWatchValue(box, spec) {
    let proto = Object.getPrototypeOf(box);
    let native = null;
    while (proto && !native) {
      native = Object.getOwnPropertyDescriptor(proto, "value");
      proto = Object.getPrototypeOf(proto);
    }
    if (!native || !native.set || Object.prototype.hasOwnProperty.call(box, "value")) return;
    let queued = false;
    Object.defineProperty(box, "value", {
      configurable: true,
      enumerable: native.enumerable,
      get() {
        return native.get.call(this);
      },
      set(next) {
        native.set.call(this, next);
        if (queued) return;
        queued = true;
        queueMicrotask(() => {
          queued = false;
          fieldClearSync(spec);
        });
      },
    });
  }

  //: The staged files in Capture are the one thing here that is not a value:
  //: their list calls this when it redraws (`renderCaptureFiles`).
  function fieldClearSyncAll() {
    for (const spec of FIELD_CLEARS) fieldClearSync(spec);
  }

  (() => {
    //: A field's own x is built here, at its top edge, not shipped in index.html:
    //: the boot page is at its element cap (tests/test_boot_diet3.py) and this
    //: file loads a few seconds after boot, long before a person types a title.
    function fieldClearInline(spec) {
      const field = document.getElementById(spec.fields[0]);
      if (!spec.inline || !field || document.getElementById(spec.button)) return;
      const anchor = document.createElement("span");
      anchor.className = "field-clear-anchor";
      const button = document.createElement("button");
      button.type = "button";
      button.id = spec.button;
      button.className = "ghost icon-only small field-clear field-clear-inline hidden";
      button.title = spec.inline;
      button.setAttribute("aria-label", spec.inline);
      const icon = document.createElement("i");
      icon.className = "ph ph-x";
      icon.setAttribute("aria-hidden", "true");
      button.append(icon);
      anchor.append(button);
      field.before(anchor);
    }

    function fieldClearWire(spec) {
      fieldClearInline(spec);
      const button = document.getElementById(spec.button);
      if (!button) return;
      button.addEventListener("click", () => fieldClearRun(spec));
      for (const box of fieldClearBoxes(spec)) {
        box.addEventListener("input", () => fieldClearSync(spec));
        box.addEventListener("change", () => fieldClearSync(spec));
        fieldClearWatchValue(box, spec);
      }
      fieldClearSync(spec);
    }

    //: A spec on a surface template (Notes, Chat, the quick note, the palette) is wired when the surface is built,
    //: not at load: a surface opened after this file loads had no box to wire (owner regression 2026-11-12).
    for (const spec of FIELD_CLEARS) {
      if (spec.surface) onSurface(spec.surface, () => fieldClearWire(spec));
      else fieldClearWire(spec);
    }
  })();

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { fieldClearSyncAll });
})();
