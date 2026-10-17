// lightbox.js: re-evaluate, inline actions, attachments, the lightbox, the
// selection popup's state. Moved out of app.js on 2026-09-26 as one contiguous
// range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md). A classic
// script sharing app.js's globals, loaded in app.js's old order; nothing in an
// earlier file calls into it while the page loads (scratchpad/appjs-map.js
// --check).



// The inline result of a re-evaluate: new confidence, plus tag and link
// suggestions the user applies with a click (nothing is applied on its own).
function renderInlineAction(entry) {
  const wrap = document.createElement("div");
  wrap.className = "inline-action";

  if (inlineAction.kind === "reevaluate") {
    renderReevaluateResult(entry, wrap);
    return wrap;
  }

  if (inlineAction.kind === "document") {
    renderAttachToDocument(entry, wrap);
    return wrap;
  }

  if (inlineAction.kind === "board") {
    renderAttachToBoard(entry, wrap);
    return wrap;
  }

  if (inlineAction.kind === "remind") {
    const shown = stripFrontmatter(entry.content).trim();
    const preview = shown.length > 40 ? shown.slice(0, 39) + "…" : shown;
    const textInput = document.createElement("input");
    textInput.type = "text";
    textInput.value = `Follow up: ${preview}`;
    const dueInput = document.createElement("input");
    dueInput.type = "datetime-local";
    dueInput.value = defaultDueValue();
    const row = document.createElement("div");
    row.className = "row";
    row.appendChild(
      smallButton("Set reminder", "", async () => {
        if (await addReminder(textInput.value.trim(), dueInput.value, entry.id)) {
          inlineAction = null;
          renderEntries();
        }
      }, false)
    );
    row.appendChild(
      smallButton("Cancel", "", () => {
        inlineAction = null;
        renderEntries();
      })
    );
    wrap.append(textInput, dueInput, row);
    setTimeout(() => textInput.focus(), 0);
    return wrap;
  }

  const isContext = inlineAction.kind === "context";

  const textarea = document.createElement("textarea");
  textarea.rows = 2;
  textarea.placeholder = isContext
    ? "Add detail: Atlas re-reads the whole note and may refile it…"
    : "Continue this train of thought…";
  wrap.appendChild(textarea);

  const row = document.createElement("div");
  row.className = "row";
  row.appendChild(
    smallButton(
      isContext ? "Add context" : "Add to thread",
      "",
      async () => {
        const text = textarea.value.trim();
        if (!text) return;
        try {
          if (isContext) {
            const updated = await apiJson(`/entries/${entry.id}/context`, {
              method: "POST",
              body: JSON.stringify({ text }),
            });
            toast(
              updated.category === entry.category
                ? `Context added: still filed under “${updated.category}”.`
                : `Context added: refiled under “${updated.category}”.`
            );
          } else {
            await apiJson("/entries", {
              method: "POST",
              body: JSON.stringify({ content: text, parent_id: entry.id }),
            });
            toast("Thread continued.");
          }
          inlineAction = null;
          await loadEntries();
        } catch (error) {
          toast(error.message, true);
        }
      },
      false
    )
  );
  row.appendChild(
    smallButton("Cancel", "", () => {
      inlineAction = null;
      renderEntries();
    })
  );
  wrap.appendChild(row);
  setTimeout(() => textarea.focus(), 0);
  return wrap;
}



// Thumbnails need the auth header, which <img src> can't send: fetch
// the bytes once per attachment and cache an object URL (Wave M).
const thumbUrlCache = new Map();

async function attachmentObjectUrl(attachment) {
  if (thumbUrlCache.has(attachment.id)) return thumbUrlCache.get(attachment.id);
  const response = await api(`/files/${attachment.id}`);
  const url = URL.createObjectURL(await response.blob());
  thumbUrlCache.set(attachment.id, url);
  return url;
}

//: **Who wrote a caption, in words** (the owner, 2026-09-24). `caption_model` names the
//: author of a caption: a vision or utility model, or `APP_CAPTION_AUTHOR`
//: when the app wrote it itself (a board export's "Part of the mind map ...,
//: exported from Tessellate", stored with `source: "app"` by routes_files.py).
//: That one is "Written by", not "Described by": nothing looked at the
//: picture. The lightbox byline and the Library card both read this, so the
//: same picture says the same thing in both places. `short` is the Library
//: card's own shortener for a long model name.
//: The sentinel is stored, so it keeps the name it was stored under; the
//: credit shows the product's current name (rebrand-1011).
const APP_CAPTION_AUTHOR = "MemoryMap"; // brand: keep
function captionCredit(model, short = (name) => name) {
  return model === APP_CAPTION_AUTHOR
    ? "Written by Tessellate"
    : `Described by ${short(model)}`;
}

// `openLightbox`, the viewer itself, is in lightbox-view.js and loads on the
// first open (app.js, `LAZY_MODULES.lightbox`); see that file's header.

// A small kebab (⋯) near whatever the user just selected, anywhere in the
// app's actual content: a document, the graph, a web search result, a chat
// message, a note. Asked for directly: "if the user highlights an output or
// piece of text... the user can save it as a note, search the notebook for
// similar phrases or meaning/topics, ask the ai about it".
//
// **It used to be three flat buttons, and the shape was the problem.** Asked
// for directly, second time round: "a kebab 3-dot button which when clicked on
// shows the Popup buttons within the application window". Three things go
// wrong with a bar that is always open, and all three are fixed by a kebab:
//
//   1. **It ran off the screen.** The old clamp was
//      `Math.min(Math.max(margin, left), innerWidth - width - margin)`. When
//      the bar is wider than the viewport the upper bound is *smaller* than
//      the lower bound, so `Math.min` wins and `left` goes negative. The bar
//      could not wrap (`white-space: nowrap`, no `flex-wrap`) and its three
//      labels ran to ~50 characters, comfortably wider than a 360px phone.
//      The clamp below is written the other way round, so a box too wide to
//      fit pins to the margin instead of hanging off the left edge.
//   2. **It covered the thing you had just selected.** A 28px dot does not.
//   3. **Three actions was the ceiling.** The app's richest capture surface
//      offered less than a note card's own ⋯ menu. A menu has room, so this
//      is now where a selection can become a note, a draft, an addition to an
//      existing note, several linked notes, a reminder, or a question.
//
// Denylist rather than an allowlist of containers: excluding form fields
// (which already have their own selection/context-menu behaviour a popup
// stealing focus would fight) and the popup's own text is simpler than
// naming every readable surface in the app and it can't silently miss one
// that gets added later.
//: Overlays are out too: the Finder, the palette and a dialog are about the
//: thing they show, and a popup offering to turn their text into a note
//: would sit over the controls a person is using.
const SELECTION_POPUP_EXCLUDED =
  "input, textarea, [contenteditable], .selection-popup, .lock-overlay, .modal-overlay, .command-palette";

let selectionPopupEl = null;
let selectionPopupText = "";
let selectionPopupSource = null;
