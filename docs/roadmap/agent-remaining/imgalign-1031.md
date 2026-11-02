# imgalign-1031 (INBOX 1465, the shared picture control)

Done: one module, `frontend/js/image-layout.js` (Library bundle, before documents.js), owns the picture options (`imageOptions`, `imageAltWith`, `imageOptionsFromAlt`, `imageApplyOptions`), the grip and align menu (`imageWireEdit`) and the note write back (`imageSaveNote`). The stored form is unchanged: the alt text, `![A river|300|center](url)`.

- Live editors (note form, graph popup, board card editor, Write with the AI, document editor) call `imageWireEdit` through `docImageLive` in documents.js.
- Every read render of note text (`notePicture` and `pictureLaidOut` in notes-list.js) draws the width, alignment and caption; a card, the timeline note view, chat and a board card's text all honour it.
- A note card and the timeline note view add the same control on first hover and save into the note (one PUT, one undo step; the readers do not run again, media_process.py `_due`).

Left, with the owner's words and where:
- Board image objects (whiteboard.js `.wb-resize-handle`) already resize; alignment means nothing for an item placed freely, so no align was added. "idk wherever notes are".
- A card's small thumbnails (`.attachment-thumb`, 110 by 180 cap, 02-chat-graph.css:2956) take the alignment and the caption but not the width, by design: a card is a list of glances. Say if the card should show pictures at their set width.
- The bin's reader and chat show the layout but have no control (no note to write to). image-layout.js `imageEditTarget` is the one place to add a surface.
- Not driven on a real board: a board card's read render goes through the same `renderMarkdown` path (whiteboard.js 6372, 10444).
- HTML export of a note is not in the app (only the document's); a note's markdown export carries the alt text as written.
