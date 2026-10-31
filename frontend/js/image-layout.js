// image-layout.js: a picture's width and alignment, drawn, edited and saved
// the same way on every surface that shows a note's image (INBOX 1465: "why
// cant I have the image alignment or resizing in the notes and boards and
// the timeline and documents editor").
//
// **The stored form is the picture's alt text**, `![A river|300|center](url)`
// (DOCUMENTS_PLAN decision 8): a width in pixels, left, center or right, and
// the rest is the caption. It is the form that travels, so the markdown
// export, the Read view, a print and another app all see the same file. Every
// surface reads it through `imageOptionsFromAlt` and draws it through
// `imageApplyOptions`; every surface writes it through `imageWireEdit`'s grip
// and align menu, so an image centred in one place is centred in all.
//
// Who calls what. The Live editor (documents.js `docImageLive`: the note form,
// the graph popup, the board card editor, the document editor) hands
// `imageWireEdit` a `write` that rewrites the alt in the editor's own text. A
// read-only draw of a note (`notePicture` in notes-list.js, which is every
// `renderMarkdown`) calls `imageLayout`; on a note card and in the timeline's
// note view the first hover over a picture adds the same grip and menu, and
// `imageSaveNote` writes the alt back into the note. Saving changes the
// note's text only: the picture's own bytes are never touched, and the
// background readers do not run again (media_process.py `_due`).
//
// Loaded with the Library bundle (app.js `LAZY_MODULES.library`) before
// documents.js. A picture drawn before this file arrives is plain; the sweep
// at the bottom lays out what is already on the page.

// IMAGE-LAYOUT-BEGIN
//: An image's `|`-separated options, by shape rather than by position.
//: `width` is a number of pixels, `align` is one of left/center/right, and
//: everything else is the caption (joined with a space, so a caption with a
//: pipe in it survives as the sentence it was).
function imageOptions(spec) {
  const parts = String(spec == null ? "" : spec).split("|");
  const name = parts.shift();
  const options = { name: (name || "").trim(), width: null, align: null, caption: "" };
  const caption = [];
  for (const raw of parts) {
    const part = raw.trim();
    if (!part) continue;
    if (/^\d{1,4}$/.test(part)) {
      options.width = Number(part);
      continue;
    }
    //: `x`-separated dimensions are Obsidian's too (`300x200`). The height is
    //: read and deliberately dropped: an image with both fixed is an image
    //: with a stretched aspect ratio, and nobody means that.
    const pair = /^(\d{1,4})x(\d{1,4})$/i.exec(part);
    if (pair) {
      options.width = Number(pair[1]);
      continue;
    }
    const align = /^(left|centre|center|right)$/i.exec(part);
    if (align) {
      options.align = align[1].toLowerCase() === "centre" ? "center" : align[1].toLowerCase();
      continue;
    }
    caption.push(part);
  }
  options.caption = caption.join(" ");
  return options;
}

//: **An image's alt with its width or alignment changed** (DOCUMENTS_PLAN
//: decision 8, the audit's D5): the name first, then the width, then the
//: alignment, then the caption's words in the order they were written; an
//: option set to null is taken out. Written back by the Live editor's grip
//: and align menu, so the markdown stays the one place the size lives.
function imageAltWith(alt, change) {
  const parts = String(alt == null ? "" : alt).split("|");
  const name = parts.shift();
  const now = imageOptions(alt);
  const kept = parts
    .map((part) => part.trim())
    .filter((part) => part && !/^\d{1,4}(x\d{1,4})?$/i.test(part) && !/^(left|centre|center|right)$/i.test(part));
  const width = "width" in change ? change.width : now.width;
  const align = "align" in change ? change.align : now.align;
  return [name, ...(width ? [String(Math.round(width))] : []), ...(align ? [align] : []), ...kept].join("|");
}

// IMAGE-LAYOUT-END

//: **A markdown image's alt text is its caption once it carries options.**
//: `![A river](/media/river.jpg)` is an image with alt text and stays one;
//: `![A river|400](/media/river.jpg)` is a figure four hundred pixels wide
//: captioned "A river", because somebody who writes an option has said this
//: image is a figure. A wiki embed does not do this and must not: the part
//: before the first pipe there is a file name, and captioning every embedded
//: picture `photo.png` is worse than captioning none of them.
function imageOptionsFromAlt(alt) {
  const text = String(alt == null ? "" : alt);
  const options = imageOptions(text);
  if (text.includes("|") && !options.caption) options.caption = options.name;
  return options;
}

//: The preview's half of the same thing. The renderer puts an image's options
//: in its `alt`, because that is where they are written in the markdown
//: (`![A river|400|center](/media/river.jpg)`), so reading them back off the
//: alt is the same information rather than a second parse of the document.
function imageLayoutRoot(root) {
  if (!root) return;
  for (const img of root.querySelectorAll("img")) {
    const alt = img.getAttribute("alt") || "";
    if (!alt.includes("|")) continue;
    const options = imageOptionsFromAlt(alt);
    img.setAttribute("alt", options.caption || options.name);
    imageApplyOptions(img, options);
  }
}

//: **An image's options, applied.** One function for both surfaces: the widget
//: in Live and the `<img>` the preview's renderer produced, because "300 means
//: 300 pixels wide" has to mean the same thing in the two views of one
//: document or the width is a property of the view rather than of the image.
//:
//: The width is written through `style.width` rather than an attribute or an
//: inline `style=`: this app's CSP refuses the attribute (DESIGN.md's note on
//: a policy silently refusing the work), and the theme's own `max-width: 100%`
//: still wins on a narrow pane, so an over-wide number cannot break the
//: column.
function imageApplyOptions(img, options) {
  if (!img || !options) return img;
  if (options.width) img.style.width = `${options.width}px`;
  if (!options.align && !options.caption) return img;
  const figure = document.createElement("span");
  figure.className = "cm-md-figure";
  if (options.align) figure.classList.add(`cm-md-figure-${options.align}`);
  if (img.parentNode) img.replaceWith(figure);
  figure.appendChild(img);
  if (options.caption) {
    const caption = document.createElement("span");
    caption.className = "cm-md-caption";
    caption.textContent = options.caption;
    figure.appendChild(caption);
  }
  return figure;
}

//: The grip and the align button on a picture (decision 8). One control for
//: every surface: `host.write(change)` is the only thing that differs (the
//: Live editor rewrites its own text, a note card or the timeline's note view
//: saves the note), and `host.widest()` is the column the picture may fill.
//: The grip is a slider to a screen reader and to the keys (the arrows, 10px;
//: with Shift, 50px), and a drag to the hand, held to between 40px and the
//: column. `host.resize === false` leaves the grip off a thumbnail, which has
//: a fixed size by design; the align button stays. Returns both controls
//: (`{ align, grip }`, the grip null on a thumbnail), so a surface can give
//: the keys back to the one that had them after its write redraws the picture
//: (WCAG 2.4.3). The align menu hands its button back as the focus's home,
//: not the invisible point it opens at.
const IMAGE_MIN = 40;

function imageWireEdit(frame, options, host) {
  const align = document.createElement("button");
  align.type = "button";
  align.className = "ghost icon-only small cm-md-image-align";
  align.setAttribute("aria-label", "Align the picture");
  align.title = "Align the picture: left, centre or right";
  const glyph = document.createElement("i");
  glyph.className = `ph ph-text-align-${options.align || "left"}`;
  glyph.setAttribute("aria-hidden", "true");
  align.appendChild(glyph);
  frame.appendChild(align);
  align.addEventListener("mousedown", (event) => event.preventDefault());
  align.addEventListener("click", (event) => {
    event.stopPropagation();
    const box = align.getBoundingClientRect();
    const pick = (value) => () => host.write({ align: value }, "align");
    openMenuAtPoint([
      makeMenuItem("ph:text-align-left Left", "On the left, text below it", pick("left")),
      makeMenuItem("ph:text-align-center Centre", "In the middle of the column", pick("center")),
      makeMenuItem("ph:text-align-right Right", "On the right", pick("right")),
      makeMenuItem("ph:text-align-justify Inline", "In the line, as written", pick(null)),
    ], "Align the picture", box.right - 8, box.bottom + 4, align);
  });
  if (host.resize === false) return { align, grip: null };
  const grip = document.createElement("span");
  grip.className = "cm-md-image-grip";
  grip.tabIndex = 0;
  grip.setAttribute("role", "slider");
  grip.setAttribute("aria-label", "Picture width");
  grip.title = "Drag to resize the picture, or use the arrow keys";
  frame.appendChild(grip);
  const shown = () => Math.round(frame.getBoundingClientRect().width);
  const setValue = () => {
    grip.setAttribute("aria-valuemin", String(IMAGE_MIN));
    grip.setAttribute("aria-valuemax", String(host.widest()));
    grip.setAttribute("aria-valuenow", String(options.width || shown() || IMAGE_MIN));
    grip.setAttribute("aria-valuetext", `${options.width || shown()} pixels wide`);
  };
  requestAnimationFrame(setValue);
  grip.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    event.stopPropagation();
    grip.setPointerCapture?.(event.pointerId);
    const startX = event.clientX;
    const start = shown();
    const max = host.widest();
    let width = start;
    frame.classList.add("is-resizing");
    const move = (e) => {
      width = Math.max(IMAGE_MIN, Math.min(max, Math.round(start + e.clientX - startX)));
      frame.style.width = `${width}px`;
      frame.dataset.sized = "1";
    };
    const up = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", up);
      grip.removeEventListener("pointercancel", up);
      frame.classList.remove("is-resizing");
      if (width !== start) host.write({ width });
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", up);
    grip.addEventListener("pointercancel", up);
  });
  grip.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 50 : 10;
    const now = options.width || shown();
    const keys = { ArrowRight: now + step, ArrowUp: now + step, ArrowLeft: now - step, ArrowDown: now - step, Home: IMAGE_MIN, End: host.widest(), Delete: 0, Backspace: 0 };
    if (!(event.key in keys)) return;
    event.preventDefault();
    event.stopPropagation();
    const next = keys[event.key];
    host.write({ width: next ? Math.max(IMAGE_MIN, Math.min(host.widest(), next)) : null }, "grip");
  });
  return { align, grip };
}

//: **A note's picture, laid out**: the hook notes-list.js calls after it has
//: put an inline picture in the page (`window.imageLayout?.(img)`, so a
//: picture drawn before this file has loaded is plain, and the sweep at the
//: bottom lays it out on arrival). The picture is framed where it stands: its
//: alt text is read for a width, an alignment and a caption, and kept whole
//: on the picture (`data-alt`) for the write back. A plain picture is framed
//: too, so the first hover can give it the grip and menu without moving
//: anything. A thumbnail (the card's `.thumb-wrap`, with its remove button)
//: keeps its size, since a card is a list of glances: it takes the alignment
//: and the caption but not the width.
function imageLayout(img) {
  if (img.dataset.alt !== undefined) return;
  const alt = img.getAttribute("alt") || "";
  const node = img.closest(".thumb-wrap") || img;
  const parent = node.parentNode;
  if (!parent) return;
  const next = node.nextSibling;
  const options = imageOptionsFromAlt(alt);
  img.alt = options.caption || options.name;
  img.dataset.alt = alt;
  let frame = node;
  if (node === img) {
    frame = document.createElement("span");
    frame.className = "cm-md-image-frame md-picture";
    frame.appendChild(img);
    if (options.width) frame.dataset.sized = "1";
  } else {
    options.width = null;
  }
  const laid = imageApplyOptions(frame, options);
  if (laid.parentNode !== parent) parent.insertBefore(laid, next);
  //: A finger has no hover: the controls are drawn (and reachable) from the start.
  if (window.matchMedia?.("(pointer: coarse)").matches) queueMicrotask(() => imageWirePicture(img));
}

//: Where a picture's note is, when the surface lets a picture be edited in
//: place: a note card in the Notes list, and the timeline's note view (which
//: marks its body). Anything else (chat, a reply, the bin's reader) is read
//: only and gets no control.
function imageEditTarget(img) {
  const marked = img.closest("[data-image-edit]");
  if (marked) return { id: marked.dataset.imageEdit, root: marked };
  const card = img.closest(".entry-content")?.closest("li[data-id]");
  return card ? { id: card.dataset.id, root: card } : null;
}

//: The note's text with this picture's markdown replaced, saved the way
//: every other note edit is saved: one PUT, one undo step, the card drawn
//: again. The markdown is looked up in the note's current text, not trusted
//: from the page, so an edit made elsewhere in the meantime is not lost; a
//: picture that has moved on says so rather than writing over it.
async function imageSaveNote(img, id, change) {
  const src = img.getAttribute("src") || "";
  const raw = `![${img.dataset.alt}](${src})`;
  const next = `![${imageAltWith(img.dataset.alt, change)}](${src})`;
  if (next === raw) return false;
  try {
    const entry = await apiJson(`/entries/${id}`);
    if (!entry.content.includes(raw)) {
      toast("That picture has changed in the note. Open the note to change it.", true);
      return false;
    }
    const content = entry.content.replace(raw, () => next);
    await apiJson(`/entries/${id}`, { method: "PUT", body: JSON.stringify({ content }) });
    pushEntryPutUndo(id, "Changed a picture", { content: entry.content }, { content });
    await refreshEntries([id]);
    return content;
  } catch (error) {
    toast(error.message || "Could not change the picture", true);
    return false;
  }
}

//: **A picture's control is added once, and before the pointer arrives.** A
//: hover (the mouse), a focus anywhere in the card (the keyboard: the Guide
//: promises the arrow keys, and a control that exists only after a pointer has
//: passed is out of reach of both the keys and a finger), and, on a touch
//: screen, as soon as the picture is laid out. The timeline's note view is
//: not a card, so it marks its body (`data-image-edit`) and hands it an
//: `imageEditAfter` to draw itself again with the saved text.
function imageWirePicture(img) {
  if (!img || img.dataset.editWired || img.dataset.alt === undefined) return;
  const target = imageEditTarget(img);
  const frame = img.closest(".cm-md-image-frame, .thumb-wrap");
  if (!target || !frame) return;
  img.dataset.editWired = "1";
  const options = imageOptionsFromAlt(img.dataset.alt);
  const thumb = frame.classList.contains("thumb-wrap");
  imageWireEdit(frame, options, {
    resize: !thumb,
    widest: () => Math.max(IMAGE_MIN, Math.floor((target.root.querySelector(".entry-content") || target.root).getBoundingClientRect().width - 16)),
    write: async (change, kind) => {
      //: Which picture of the note this is, and whether the keys were on its
      //: grip or its align button, read before the save redraws both.
      const at = [...target.root.querySelectorAll("img[data-alt]")].indexOf(img);
      const held = kind && frame.contains(document.activeElement) ? kind : null;
      const content = await imageSaveNote(img, target.id, change);
      if (content === false) return;
      if (target.root.imageEditAfter) target.root.imageEditAfter(content);
      if (held) imageRefocus(target.id, target.root.dataset.imageEdit !== undefined, at, held);
    },
  });
}

//: The control that had the keys, found again on the redrawn picture: the card
//: or the note view is looked up afresh (the save replaced them), and a
//: thumbnail, which has no grip, hands its align button the keys instead.
function imageRefocus(id, marked, at, held) {
  const root = document.querySelector(marked ? `[data-image-edit="${id}"]` : `li[data-id="${id}"]`);
  const img = root?.querySelectorAll("img[data-alt]")[at];
  if (!img) return;
  imageWirePicture(img);
  const frame = img.closest(".cm-md-image-frame, .thumb-wrap");
  const control = (held === "grip" && frame?.querySelector(".cm-md-image-grip")) || frame?.querySelector(".cm-md-image-align");
  control?.focus({ preventScroll: true });
}

//: Every picture under a card or a note view, wired (the timeline calls this
//: after it draws its body; the card's focus does through `imageFocusEdit`).
function imageWireAll(root) {
  for (const img of root.querySelectorAll("img[data-alt]:not([data-edit-wired])")) imageWirePicture(img);
}

function imageHoverEdit(event) {
  imageWirePicture(event.target instanceof Element ? event.target.closest("img[data-alt]") : null);
}

function imageFocusEdit(event) {
  const card = event.target instanceof Element ? event.target.closest("li[data-id]") : null;
  if (card) imageWireAll(card);
}

document.addEventListener("pointerover", imageHoverEdit);
document.addEventListener("focusin", imageFocusEdit);

//: Pictures drawn before this file arrived (the first seconds of a session, a
//: connection saving data) are plain; lay them out now.
for (const img of document.querySelectorAll(".entry-inline-image, .attachment-thumb")) imageLayout(img);
