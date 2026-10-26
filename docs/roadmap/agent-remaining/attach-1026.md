# attach-1026: chat attachments, the popup agent's attach, a notification's Library tab, OCR workbench speed

The owner, 2026-10-26, verbatim (with three screenshots: the Chat composer's
attachment chip, the popup agent's box holding a raw `[name.pdf](/media/...pdf)`
link, the Library opened on Images):

> "can ther ebe better modern and proffessional this app styled attachment chips
> and the like on the chat interfaces? also if i attach documents tot he popup
> agent, they arent chipped so I cant remove them, like what if I upload a
> document but I dont want it saved to the app and I want to delete it before I
> send it?? also it only accepts images and pdfs, the popup agent attachment
> redesign needs imporvement as ewell. also I clicked a notification to see a pdf
> I uploaded and it took me tot he library images tab not the files tab in the
> library"

> "also clicking between the ocr workbench left sidebar headers for files and
> pages like going between files really quick and viweing the pages and the pages
> loading and the page number in the top pill updating is slow and laggy and not
> fast"

## Rows (agent attach, Opus for the design rows; ocrspeed, Sonnet)

- [x] A1 (done: `attachmentChip` in chat-attach.js, DESIGN.md row, lint `test_one_attachment_chip_serves_chat_and_the_popup_agent`; `ui-sweeps/attachchips.js` 36 checks ok at 1440, 720, 390: chip 51px high, x 24px+ and labelled, extension kept when the stem is cut. Ask has no attachment strip, so it has no chip; Chat's note, map, selection and web chips stay the one-line `.attachment-chip`) One attachment chip recipe for every chat surface (Chat composer, popup agent, Ask): file-type icon or image thumbnail, name with a middle ellipsis that keeps the extension, size, upload progress, a remove button, error state; a DESIGN.md recipe and its lint in the same commit (standing order 11). Measure against Claude, ChatGPT and Notion chips.
- [x] A2 (done: staged in the browser, uploaded only on Enter, so remove-before-send has nothing on the server to delete; a failed send deletes the media already uploaded via DELETE /media/{id}; sweep: 0 upload requests while staging and removing) Popup agent: attachments become chips, not a markdown link in the text box; removing one before sending deletes the upload (an attached file is not kept in the Library until the message is sent; say so in the chip's title).
- [x] A3 (done: paperclip, drop and paste stage any kind; images to /media/upload, the rest to /documents/import with the Chat PDF fallback; sweep: send makes one media upload and one import, no 415; found-not-fixed: Chat's own drop and paste still refuse non-images with a toast, settings-wiring.js, only its picker takes documents) (log, 15:02: "[HTTP 415] POST /media/upload: Only images and PDFs can be dropped in here") Popup agent accepts what Chat accepts (documents, text, code, audio as Chat does), not only images and PDFs; drag and drop and paste.
- [x] A4 (done: file-drop.js notice and its bell row carry `go.media`, notifications.js opens the sub-tab, the Chat kept-PDF notice too; `runNotificationGo({tab:'library',media:'files'})` selects Files) Bug: a notification about an uploaded PDF opens Library > Images; it must open Library > Files at that file.
- [ ] O1 OCR workbench: switching files and pages in the left sidebar is slow; the page and the top pill's page number lag. Measure first (lag-watch.js now logs the frames and their scripts), then render the visible page first, cache rendered pages, cancel a stale render when another file is picked, update the pill at once.
- [ ] O2 The owner: "I think it waits for rapid ocr or tesserract to read the whole ndocument first before loading the other pages". Check whether a page view waits on the whole-document OCR job; show each page image as soon as it renders and fill its text when that page's OCR lands.
- [ ] O3 The owner: "also rendering the regions on pdfs is a little flashy and on and off". Region overlays redraw from empty on each update; diff them in place (keep nodes, change only what moved) so they never blink.
