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

- [ ] A1 One attachment chip recipe for every chat surface (Chat composer, popup agent, Ask): file-type icon or image thumbnail, name with a middle ellipsis that keeps the extension, size, upload progress, a remove button, error state; a DESIGN.md recipe and its lint in the same commit (standing order 11). Measure against Claude, ChatGPT and Notion chips.
- [ ] A2 Popup agent: attachments become chips, not a markdown link in the text box; removing one before sending deletes the upload (an attached file is not kept in the Library until the message is sent; say so in the chip's title).
- [ ] A3 (log, 15:02: "[HTTP 415] POST /media/upload: Only images and PDFs can be dropped in here") Popup agent accepts what Chat accepts (documents, text, code, audio as Chat does), not only images and PDFs; drag and drop and paste.
- [ ] A4 Bug: a notification about an uploaded PDF opens Library > Images; it must open Library > Files at that file.
- [ ] O1 OCR workbench: switching files and pages in the left sidebar is slow; the page and the top pill's page number lag. Measure first (lag-watch.js now logs the frames and their scripts), then render the visible page first, cache rendered pages, cancel a stale render when another file is picked, update the pill at once.
- [ ] O2 The owner: "I think it waits for rapid ocr or tesserract to read the whole ndocument first before loading the other pages". Check whether a page view waits on the whole-document OCR job; show each page image as soon as it renders and fill its text when that page's OCR lands.
- [ ] O3 The owner: "also rendering the regions on pdfs is a little flashy and on and off". Region overlays redraw from empty on each update; diff them in place (keep nodes, change only what moved) so they never blink.
