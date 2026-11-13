(() => {
  // whiteboard-pdf.js: a PDF dropped, pasted or chosen on a board (L-whiteboard-2, the owner's INBOX B74: "a PDF or document
  // viewer object ... or place each page as a separate image, print it out, like OneNote"). The question is asked once
  // ("Place as pages" or "Attach as one object"); either answer is one Undo step. The pages are the ones the file viewer
  // already draws (GET /media/pdf-page/{name}/{n}, rasterised by the server), so nothing new is fetched or installed.
  // Joins `wbFmtState` (whiteboard-format.js); names whiteboard.js and app.js at run time only.
  const MAX_PAGES = 20;
  const PAGE_WIDTH = 320;
  const GAP = 24;
  const CAP = 50 * 1024 * 1024;

  const isPdf = (file) => !!file && (file.type === "application/pdf" || /\.pdf$/i.test(file.name || ""));
  const pageUrl = (stored, index) => `/media/pdf-page/${encodeURIComponent(stored)}/${index}`;

  //: The page's own proportions, from its picture; a letter-shaped guess when it will not load.
  function pageShape(url) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img.naturalHeight / Math.max(1, img.naturalWidth));
      img.onerror = () => resolve(1.414);
      img.src = mediaSrc(url);
    });
  }

  async function upload(file) {
    const form = new FormData();
    form.append("file", file);
    form.append("board", "true");
    const up = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form });
    return { stored: String(up.url || "").split("/").pop(), name: up.original_name || file.name || "document.pdf" };
  }

  //: How many pages the server can draw: 0 when it has no rasteriser (an optional package) or cannot open the file.
  async function pageCount(stored) {
    try {
      const info = await apiJson(`/media/pdf-info/${encodeURIComponent(stored)}`);
      return info?.available ? Math.max(0, info.pages | 0) : 0;
    } catch {
      return 0;
    }
  }

  //: true: pages, false: one object, undefined: the person backed out. Cancel is "Attach" so Escape and the backdrop stay a no.
  function ask(name, pages) {
    const shown = Math.min(pages, MAX_PAGES);
    const note = pages > MAX_PAGES ? ` Only the first ${MAX_PAGES} of ${pages} pages are placed.` : "";
    return confirmDialog(`Add ${name} to the board?\n\nPlace it as ${shown} separate ${shown === 1 ? "picture" : "pictures"}, or keep it as one object that opens the file.${note}`, {
      confirmLabel: "Place as pages", cancelLabel: "Attach as one object", danger: false,
    });
  }

  //: The pages side by side, centred on (x, y).
  async function placePages(info, pages, x, y) {
    const count = Math.min(pages, MAX_PAGES);
    const height = Math.round(PAGE_WIDTH * (await pageShape(pageUrl(info.stored, 0))));
    const left = x - (count * PAGE_WIDTH + (count - 1) * GAP) / 2;
    for (let i = 0; i < count; i++) {
      await wbCreateObject("image", { url: pageUrl(info.stored, i), pdf: `/media/${info.stored}`, pdf_name: info.name },
        Math.round(left + i * (PAGE_WIDTH + GAP)), Math.round(y - height / 2), PAGE_WIDTH, height);
    }
    return count;
  }

  //: One object that shows page 1; a text card with the name when no page can be drawn.
  async function placeOne(info, pages, x, y) {
    if (!pages) {
      await wbCreateObject("text", { content: `${info.name}\nPDF, double-click to open`, pdf: `/media/${info.stored}`, pdf_name: info.name },
        Math.round(x - 110), Math.round(y - 40), 220, 80);
      return;
    }
    const height = Math.round(PAGE_WIDTH * (await pageShape(pageUrl(info.stored, 0))));
    await wbCreateObject("image", { url: pageUrl(info.stored, 0), pdf: `/media/${info.stored}`, pdf_name: info.name },
      Math.round(x - PAGE_WIDTH / 2), Math.round(y - height / 2), PAGE_WIDTH, height);
  }

  async function place(file, x, y) {
    if (file.size > CAP) return toast("That PDF is over 50 MB, the most the notebook keeps.", "info");
    try {
      const info = await upload(file);
      const pages = await pageCount(info.stored);
      const choice = pages ? await ask(info.name, pages) : false;
      if (choice === undefined) return;
      await wbRecordGesture(async () => {
        if (choice) {
          const n = await placePages(info, pages, x, y);
          toast(pages > MAX_PAGES ? `Placed the first ${MAX_PAGES} of ${pages} pages.` : `Placed ${n} ${n === 1 ? "page" : "pages"}.`);
        } else await placeOne(info, pages, x, y);
      });
    } catch (err) {
      toast(err.message || "Couldn't add that PDF.", "info");
    }
  }

  //: The file behind an object, in the viewer the Library uses.
  function open(object) {
    const url = object?.data?.pdf;
    if (!url || typeof openLightbox !== "function") return false;
    openLightbox([{ filename: url.split("/").pop(), getUrl: () => mediaSrc(url) }], 0);
    return true;
  }

  function onDblClick(event) {
    if (event.target.closest?.(".wb-resize-handle, .wb-rotate-handle")) return;
    const el = event.target.closest?.(".wb-object");
    const object = el && (wbState?.objects || []).find((o) => o.id === Number(el.dataset.id));
    if (object?.data?.pdf && open(object)) {
      event.preventDefault();
      event.stopPropagation();
    }
  }
  document.addEventListener("dblclick", onDblClick, true);

  Object.assign(wbFmtState, { pdf: { isPdf, place, open, MAX_PAGES } });
})();
