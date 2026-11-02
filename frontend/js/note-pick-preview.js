// note-pick-preview.js: what the "[[" picker's preview pane shows for a note:
// a short excerpt and its first picture. Moved out of rich-picker.js
// (`richPickerLines`) into a lazy file on 2026-10-10 (the boot-script gzip
// budget, tests/test_boot_budget.py): only a "[[" row that is a note draws
// it. It rides the note panels' bundle (`LAZY_MODULES.notePanels`, preloaded
// three seconds after boot), and `editorRenderPreview` (editor.js) has
// already drawn the pane's head, so the pane is right while this loads and
// gains the excerpt a moment later.
//
// The title is said once, by the pane's head, and never again below it: a
// note a sketch saved is "Title, then the drawing with the title as its alt
// text", and every line of it flattened to text read as the title four times
// (INBOX 784). So the excerpt skips a line equal to the title, a line that is
// only a picture, and a line it has already shown.

const NOTE_PICK_LINES = 3;
const NOTE_PICK_LINE_CHARS = 120;
const NOTE_PICK_IMAGE = /!\[[^\]\n]{0,200}\]\(([^)\s\n]{1,500})[^)\n]*\)/;

function notePickText(line) {
  return notePreviewText(line.replace(new RegExp(NOTE_PICK_IMAGE.source, "g"), "")).replace(/\s+/g, " ").trim();
}

//: The lines an excerpt shows: `[]` for a note that is its title and a picture.
function notePickExcerpt(content) {
  const lines = stripFrontmatter(content || "").split("\n");
  const title = notePickText(lines.find((line) => notePickText(line)) || "").toLowerCase();
  const seen = new Set([title]);
  const out = [];
  for (const line of lines) {
    const text = notePickText(line);
    const key = text.toLowerCase();
    if (!text || seen.has(key)) continue;
    seen.add(key);
    out.push(text.length > NOTE_PICK_LINE_CHARS ? `${text.slice(0, NOTE_PICK_LINE_CHARS - 1)}…` : text);
    if (out.length >= NOTE_PICK_LINES) break;
  }
  return out;
}

//: The note's first picture, drawn the way its card draws one: an inline
//: image through `mediaSrc`, else an attached one through
//: `attachmentObjectUrl`. Null when it has none.
function notePickThumb(entry) {
  const img = document.createElement("img");
  img.className = "attachment-thumb";
  img.alt = "";
  const inline = String(entry.content || "").match(NOTE_PICK_IMAGE);
  //: Not a picture at another address: the page refuses it, and asking logs a CSP error (audit 1029 row 45).
  if (inline && isRenderableUrl(inline[1]) && !isRemoteImage(inline[1])) {
    img.src = mediaSrc(inline[1]);
    return img;
  }
  const attached = (entry.attachments || []).find((a) => a.is_image);
  if (!attached) return null;
  attachmentObjectUrl(attached).then((url) => (img.src = url)).catch(() => img.remove());
  return img;
}

function richPickerNote(pane, item) {
  const sample = document.createElement("div");
  //: The picture first: the pane fades out at its foot, which is a kinder
  //: place for a line of text to end than a picture's lower edge.
  const thumb = notePickThumb(item.entry);
  if (thumb) sample.appendChild(thumb);
  for (const text of notePickExcerpt(item.entry.content)) {
    const p = document.createElement("p");
    p.textContent = text;
    sample.appendChild(p);
  }
  //: A quick arrow through the list asks for several before the first file
  //: lands: only the row the pane is still on draws.
  if (!sample.childElementCount || pane.dataset.for !== item.id) return;
  sample.classList.add("rich-picker-sample");
  sample.inert = true;
  pane.appendChild(sample);
}
