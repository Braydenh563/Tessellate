// The lightbox viewer, loaded on its first open (app.js, `LAZY_MODULES.lightbox`).
//
// Split out of lightbox.js on 2026-09-27 when the app's boot scripts passed
// their gzip budget (`tests/test_static_compression.py`, TOTAL_CAP): this one
// function was 1,868 of that file's 2,303 lines, every caller ignores what it
// returns, and nothing needs it until an image is opened, so it is the
// cheapest honest surface to take off the cold load. The attachment helpers
// the rest of the app calls at boot (`attachmentObjectUrl`, `attachFileTo`,
// the re-evaluate row) stay in lightbox.js. Until this file arrives,
// `openLightbox` is app.js's stand-in, which loads it and then calls the real
// one; a classic script's top-level function replaces the stand-in on load.

// Full-size image viewer: click anywhere or press Esc to close (Wave M).
// `items` is every image this click can page through, e.g. all the image
// attachments on the same note, as `{filename, getUrl}`, `getUrl` being a
// (possibly async) thunk so unopened images aren't fetched until reached.
// `startIndex` is which one was clicked; a single image is just a one-item
// list. Reported directly: click-anywhere-to-close alone isn't discoverable,
// so there's now an explicit close button too, both still work.
//: `opts.focusReading` opens the dialog *at the reading* rather than at the
//: top of the file, Phase 7.5's "an 'Open reading' action that opens the
//: lightbox at the reading". On a tall document the info panel is below the
//: fold, so a plain open lands the reader on a page and leaves them to find
//: the text they asked for.
//: The viewer's '?' popover: the gestures and keys no button shows.
const LIGHTBOX_HELP = [
  "Scroll to zoom where the pointer is, drag to move a zoomed picture, and double-click to switch between fit and actual size.",
  "Keys: Left and Right move between files, plus and minus zoom, 0 fits, 1 shows actual size, R rotates, I shows or hides the details, Escape closes.",
  "On a touch screen, swipe sideways to move between files and pinch to zoom.",
  "The bars fade when the mouse rests on the picture and come back when it moves.",
];

function openLightbox(items, startIndex = 0, opts = {}) {
  let index = startIndex;
  const overlay = document.createElement("div");
  overlay.className = "lightbox";
  // Not decoration: this is what puts the lightbox inside `activeOverlay()`'s
  // reach (see its comment), and it is what a screen reader needs to announce
  // the thing as a dialog rather than as a stray region.
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Image viewer");
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-label", "Image preview");

  //: **The viewer's chrome** (INBOX 1300 C30, the owner: "Can the lightbox
  //: controls and elements have a new redesign and upgrade in ui and ux
  //: usability??"). Measured before (scratchpad/ui-sweeps/lightbox1300.js):
  //: every control in one wrapping row under the picture, the name and
  //: "N of M" in a line of grey text, a lone round X in the corner, no
  //: keys but the arrows and Escape, no swipe or pinch, and a picture 7% of
  //: a phone's screen. Now two `.dock`s on the panel ground, floating over
  //: the scrim: the top bar says what this is and acts on the file (copy,
  //: download, open, details, help, the ⋯, close), the foot holds the view
  //: (zoom, fit, actual size, rotate, the page stepper) with a filmstrip
  //: above it when there is more than one file. Both fade on an idle mouse
  //: and come back on any movement, never for keys or reduced motion.
  const topbar = document.createElement("div");
  topbar.className = "dock lightbox-topbar";
  topbar.setAttribute("role", "toolbar");
  topbar.setAttribute("aria-label", "File");
  const topIdentity = document.createElement("div");
  topIdentity.className = "dock-identity";
  const title = document.createElement("h2");
  title.className = "lightbox-title";
  const position = document.createElement("span");
  position.className = "dock-chip lightbox-position";
  topIdentity.append(title, position);
  const topActions = document.createElement("div");
  topActions.className = "dock-actions lightbox-top-actions";
  topbar.append(topIdentity, topActions);
  topbar.addEventListener("click", (e) => e.stopPropagation());
  const syncTitle = (item) => {
    title.textContent = item?.filename || "Untitled file";
    title.title = item?.filename || "";
    position.textContent = items.length > 1 ? `${index + 1} of ${items.length}` : "";
  };

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "ghost small icon-only lightbox-close";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.title = "Close (Esc)";
  // A raw "×" character, not an icon-font glyph, reported live as still
  // off-centre even inside the `display:grid;place-items:center` box that
  // fixed every *padding*-driven case of this: `place-items` centres the
  // line box, not necessarily where a font renders that specific character's
  // ink within it, and that varies by system font. Every other close button
  // in the app already uses the ph:x icon glyph for exactly this reason, 
  // matching it here fixes the centring and the inconsistency together.
  setLabel(closeBtn, "ph:x");

  const img = document.createElement("img");
  const broken = document.createElement("p");
  broken.className = "lightbox-broken hidden";

  // What the app knows *about* the picture, shown with the picture. Asked for
  // directly: "if clicking on an image to view expand it in the lightbox…can
  // the captions and ocr accompany it somehow??", before this, the caption a
  // vision model wrote and the text it read off the page existed only on the
  // Library tile, which is the one view too small to read them in. Optional
  // per item (`caption`, `text`, and their bylines): every other caller
  // passes only `{filename, getUrl}` and gets exactly what it got before.
  // Mirrors `syncCaptionBadge` on the Library tile (library.js) exactly, so
  // the same picture says the same thing in both places: which model wrote
  // the description, and whether a person has since changed it.
  const captionBylineFor = (row) => {
    if (!row || !row.caption) return "";
    const parts = [];
    if (row.caption_model) parts.push(captionCredit(row.caption_model));
    if (row.caption_edited) parts.push(row.caption_model ? "edited" : "typed by hand");
    return parts.join(" · ");
  };

  const info = document.createElement("div");
  info.className = "lightbox-info hidden";
  const infoCaption = document.createElement("p");
  infoCaption.className = "lightbox-caption";
  // Who wrote the caption. Reported directly: "there is also no 'text read
  // by' line in the lightbox for the image captions, only the ocr", the
  // Library tile has carried a caption byline (`captionBadge`, library.js)
  // since captions could be edited by hand, and only the lightbox was
  // missing its half, so the same picture named its transcriber but not its
  // describer.
  const infoCaptionByline = document.createElement("p");
  infoCaptionByline.className = "lightbox-byline";
  const infoText = document.createElement("p");
  infoText.className = "lightbox-text";
  const infoByline = document.createElement("p");
  infoByline.className = "lightbox-byline";
  //: The second reader's answer to the same question, under the first one's,
  //: in the same two elements the first one uses: see `lightboxReadingsFor`
  //: for why it is here at all and why it is not a toggle. Both are hidden
  //: together, so a picture with one reading looks exactly as it did.
  const infoAltText = document.createElement("p");
  infoAltText.className = "lightbox-text lightbox-alt-text";
  const infoAltByline = document.createElement("p");
  infoAltByline.className = "lightbox-byline";
  //: **Each reading can be deleted where it is shown** (INBOX 421 e, the
  //: owner: "I cant delete the ocr entry in ... the lightbox"). The OCR
  //: workspace had a Delete reading and this panel, the other place a reading
  //: is read, had none, so a wrong one (a model's "Test, Test, Test" loop)
  //: could only be removed by opening the workspace. One trash button at the
  //: end of each reading's byline, clearing that reading's own field
  //: (`textSource`/`altSource` from `lightboxReadingsFor`), confirmed first,
  //: the workspace's own wording. Only for a picture with a media row: a url
  //: with nothing behind it has nothing to delete.
  const readingDelete = (which) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small icon-only danger lightbox-reading-delete hidden";
    button.title = "Delete this reading";
    button.setAttribute("aria-label", "Delete this reading");
    setLabel(button, "ph:trash");
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      //: Held before the first `await`: `currentTarget` is gone once the
      //: click's dispatch ends (the workspace's own Delete reading lost its
      //: button that way, 6e072b2).
      const self = event.currentTarget;
      const item = lightboxInfoItem || items[index];
      const source = which === "alt" ? item?.altSource : item?.textSource;
      const id = lightboxMediaId(item);
      if (!item || !source || !id) return;
      const whose = source === "vision" ? "the vision model's" : "Tesseract's";
      if (!(await confirmDialog(`Delete ${whose} reading of this image? You can read it again any time.`))) return;
      self.disabled = true;
      try {
        //: To the reading bin, not away (the OCR workspace's own route): Undo
        //: restores that row, Redo bins the reading again. The panel is
        //: redrawn from the fields it held, as they were and as they become.
        const bin = () => apiJson(`/media/${id}/readings/${source}`, { method: "DELETE" });
        const fields = ["text", "byline", "altText", "altByline", "textSource", "altSource"];
        const was = Object.fromEntries(fields.map((key) => [key, item[key]]));
        const now =
          source === item.textSource
            ? { text: item.altText || "", byline: item.altText ? "Text read with Tesseract OCR" : "", altText: "", altByline: "", textSource: item.altSource || "", altSource: "" }
            : { altText: "", altByline: "", altSource: "" };
        const repaint = (values) => {
          Object.assign(item, values);
          if (overlay.isConnected) renderInfo(item, true);
          if (typeof loadLibrary === "function") loadLibrary();
        };
        let held = (await bin())?.binned_id;
        repaint(now);
        toast("Reading deleted.");
        pushUndo(
          "Deleted a reading",
          async () => {
            if (held) await apiJson(`/reading-bin/${held}/restore`, { method: "POST" });
            repaint(was);
          },
          async () => {
            held = (await bin())?.binned_id;
            repaint(now);
          }
        );
      } catch (err) {
        toast(err.message || "Could not delete that reading.", true);
      } finally {
        self.disabled = false;
      }
    });
    return button;
  };
  const infoTextDelete = readingDelete("text");
  const infoAltDelete = readingDelete("alt");
  const bylineRow = (byline, remove) => {
    const row = document.createElement("div");
    row.className = "lightbox-byline-row";
    row.append(byline, remove);
    return row;
  };
  // Dimensions, when it was added, the filename, the "other info about it"
  // half of the request. First, because it is the line that says *which*
  // picture this is; the readings below it are about what is in it.
  const infoFacts = document.createElement("p");
  infoFacts.className = "lightbox-facts";
  //: **What only a document has** (UI_MODERNISATION_PLAN Phase 7.1). Reported:
  //: "the lightbox needs improving for file and pdf previews, no sections or
  //: info are below it really compared to the images." An image already got
  //: facts, caption, reading and bylines under it; a PDF got the pages and
  //: nothing else: and the three things a *document* can say that a
  //: photograph cannot (how many pages it has, which of them have been read,
  //: and which one you are looking at) had nowhere to be said.
  //:
  //: One row of `.chip`s, one per page, in the panel that already exists, 
  //: not a second info block. A chip is a page: it says whether that page has
  //: a stored reading, and clicking it scrolls the pages column to it, which
  //: is also what makes "open the reader at *this* page" a meaningful offer.
  const infoPages = document.createElement("div");
  infoPages.className = "row lightbox-pages hidden";
  info.append(
    infoFacts,
    infoPages,
    infoCaption,
    infoCaptionByline,
    infoText,
    bylineRow(infoByline, infoTextDelete),
    infoAltText,
    bylineRow(infoAltByline, infoAltDelete)
  );
  //: The media row a reading can be deleted from: the Library's own items
  //: carry it as `id` (and a document as `kind`, which has no such row); a
  //: picture opened from a note or a chat learns it from `/media/meta`.
  function lightboxMediaId(item) {
    if (!item || item.kind) return null;
    return item.id || item.metaId || null;
  }
  //: Shown only beside a reading that is on screen and deletable. Not on a
  //: document's page: that text is the page's own `PageRead`, deleted from
  //: the workspace, not a field of the file.
  function syncReadingDeletes(item, { text = "", alt = "", perPage = false } = {}) {
    const id = lightboxMediaId(item);
    infoTextDelete.classList.toggle("hidden", perPage || !id || !text || !item?.textSource);
    infoAltDelete.classList.toggle("hidden", perPage || !id || !alt || !item?.altSource);
  }

  //: Drawn from one place, because both `show()` and `renderInfo` paint this
  //: panel and a second reading left behind by the previous picture is worse
  //: than never showing one at all.
  function renderAltReading(text, byline) {
    const alt = (text || "").trim();
    infoAltText.textContent = alt;
    infoAltText.classList.toggle("hidden", !alt);
    infoAltByline.textContent = alt ? byline || "" : "";
    infoAltByline.classList.toggle("hidden", !alt || !byline);
  }
  // Clicking the panel must not dismiss the dialog, someone selecting a line
  // of transcribed text to copy is the whole reason it is here.
  info.addEventListener("click", (e) => e.stopPropagation());

  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "lightbox-nav lightbox-prev";
  prevBtn.setAttribute("aria-label", "Previous image");
  setLabel(prevBtn, "ph:caret-left");

  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "lightbox-nav lightbox-next";
  nextBtn.setAttribute("aria-label", "Next image");
  setLabel(nextBtn, "ph:caret-right");
  prevBtn.title = "Previous (Left arrow)";
  nextBtn.title = "Next (Right arrow)";

  //: The view's dock, at the foot. Its groups are the dock recipe's zones:
  //: where you are (phone only: the side arrows leave a 390px screen's
  //: picture 233px wide, so there they live here), how big, which page.
  const dock = document.createElement("div");
  dock.className = "dock lightbox-dock";
  dock.setAttribute("role", "toolbar");
  dock.setAttribute("aria-label", "View");
  dock.addEventListener("click", (e) => e.stopPropagation());
  const dockZone = (name) => {
    const zone = document.createElement("div");
    zone.className = `dock-group lightbox-dock-${name}`;
    dock.appendChild(zone);
    return zone;
  };
  const dockPrevZone = dockZone("prev");
  const dockZoomZone = dockZone("zoom");
  const dockViewZone = dockZone("view");
  const dockPageZone = dockZone("page");
  const dockNextZone = dockZone("next");
  const bottom = document.createElement("div");
  bottom.className = "lightbox-bottom";

  //: **The filmstrip**: every file this view can page through, one press
  //: away, the current one marked. A picture's thumbnail is fetched when its
  //: tile scrolls into the strip, not before (`getUrl` may be a request, and
  //: a gallery of two hundred should not make two hundred on open). One tab
  //: stop: the current tile; the arrows move it.
  const film = document.createElement("div");
  film.className = "lightbox-filmstrip";
  film.setAttribute("role", "group");
  film.setAttribute("aria-label", "Files in this view");
  film.addEventListener("click", (e) => e.stopPropagation());
  let filmSeen = null;
  const fileGlyph = (name) =>
    /\.pdf$/i.test(name) ? "file-pdf" : /\.(docx?|odt|rtf)$/i.test(name) ? "file-doc" : /\.(md|txt|csv|json|html?)$/i.test(name) ? "file-text" : "file";
  function renderFilmstrip() {
    filmSeen?.disconnect();
    film.replaceChildren();
    overlay.classList.toggle("lightbox-has-film", items.length > 1);
    if (items.length < 2) return;
    filmSeen = new IntersectionObserver(
      (seen) => {
        for (const entry of seen) {
          if (!entry.isIntersecting) continue;
          filmSeen.unobserve(entry.target);
          const it = items[Number(entry.target.dataset.index)];
          const pic = entry.target.querySelector("img");
          if (it && pic) Promise.resolve(it.getUrl()).then((src) => { if (src) pic.src = src; }).catch(() => {});
        }
      },
      { root: film, rootMargin: "0px 160px" }
    );
    items.forEach((it, i) => {
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = "lightbox-thumb";
      tile.dataset.index = String(i);
      tile.tabIndex = -1;
      tile.title = it.filename || "";
      tile.setAttribute("aria-label", `${it.filename || "File"}, ${i + 1} of ${items.length}`);
      if (IMAGE_SUFFIXES.test(it.filename || "") && !it.kind) {
        const pic = document.createElement("img");
        pic.alt = "";
        pic.decoding = "async";
        tile.appendChild(pic);
        if (filmSeen) filmSeen.observe(tile);
        else Promise.resolve(it.getUrl()).then((src) => { if (src) pic.src = src; }).catch(() => {});
      } else {
        const glyph = document.createElement("i");
        glyph.className = `ph ph-${fileGlyph(it.filename || "")}`;
        glyph.setAttribute("aria-hidden", "true");
        tile.appendChild(glyph);
      }
      tile.addEventListener("click", () => show(i));
      film.appendChild(tile);
    });
  }
  const syncFilmstrip = () => {
    if (film.childElementCount !== (items.length > 1 ? items.length : 0)) renderFilmstrip();
    const hadFocus = film.contains(document.activeElement);
    for (const tile of film.children) {
      const here = Number(tile.dataset.index) === index;
      tile.classList.toggle("is-current", here);
      tile.tabIndex = here ? 0 : -1;
      if (here) tile.setAttribute("aria-current", "true");
      else tile.removeAttribute("aria-current");
    }
    const current = film.children[index];
    if (!current) return;
    if (hadFocus) current.focus({ preventScroll: true });
    //: Centred in the strip by its own scroll, never `scrollIntoView`, which
    //: would also scroll the dialog behind it.
    const strip = film.getBoundingClientRect();
    const box = current.getBoundingClientRect();
    film.scrollLeft += box.left + box.width / 2 - (strip.left + strip.width / 2);
  };

  // **The arrows are centred by the layout now, not by a measurement.**
  //
  // They used to be `position: fixed` at `top: 50%`, which is the viewport's
  // centre and not the image's; a previous fix measured the image's rendered
  // box on every `show()` and wrote a `top` back. That worked while the
  // lightbox was one centred stack, and stopped working the moment it grew a
  // scrollable info panel: reported with a screenshot of both arrows sitting
  // level with the top edge of the picture.
  //
  // The fix is structural: the image and the two arrows share a positioned
  // wrapper, so `top: 50%; translateY(-50%)` is the middle of the *image*, at
  // every size, at every scroll offset, with no JS and nothing to keep in
  // sync. `positionNav`, its `resize` listener and its two callers are gone.
  const stage = document.createElement("div");
  stage.className = "lightbox-stage";

  // **The actions bar.** Asked for directly: "improve on and expand the
  // capabilities and features at the bottom of the lightbox". Until now the
  // lightbox was purely an *information* surface, filename, dimensions,
  // caption, OCR text: with no action on it at all, which meant the one
  // place you are actually looking at a picture was the one place you could
  // not do anything to it.
  //
  // Everything here works from what `openLightbox` already receives, so it
  // lights up for **every** caller (notes, chat, graph, dashboard, library)
  // rather than only the Library's richer items. Actions that need a media
  // id, describe with AI, re-run OCR, rename, delete, are deliberately
  // not here: no caller passes one today, and inventing a half-working row
  // that only the Library populates is the "two buttons guaranteed to fail"
  // shape this project has already rejected once on the whiteboard menu.
  const actions = document.createElement("div");
  actions.className = "lightbox-actions";
  actions.addEventListener("click", (e) => e.stopPropagation());

  // Zoom is the gap that mattered most: a lightbox that cannot magnify is
  // just a bigger thumbnail, and the OCR panel below is often the only way
  // to read text in a picture precisely because you could not zoom into it.
  let zoom = 1;
  let panX = 0;
  let panY = 0;
  //: Quarter turns, kept cumulative (90, 180, 270, 360...) so the eased
  //: transform always turns the same way rather than unwinding at 360.
  let rotation = 0;
  const ZOOM_MIN = 1;
  const zoomLabel = document.createElement("span");
  zoomLabel.className = "lightbox-zoom-label";
  const reducedMotion = () => reducedMotionWanted();
  //: A turned picture is fitted again: a wide photo stood on its end is as
  //: tall as it was wide, so it is scaled into the box it had.
  const turnFit = () => {
    if (!(rotation % 180)) return 1;
    const w = img.offsetWidth;
    const h = img.offsetHeight;
    if (!w || !h) return 1;
    const maxH = parseFloat(getComputedStyle(img).maxHeight) || h;
    return Math.min(1, stage.clientWidth / h, maxH / w);
  };
  //: The zoom at which one picture pixel is one CSS pixel ("actual size").
  const actualZoom = () =>
    img.naturalWidth && img.offsetWidth ? img.naturalWidth / (img.offsetWidth * turnFit()) : 1;
  const zoomMax = () => (zoomTarget() === img ? Math.min(32, Math.max(6, actualZoom() * 2)) : 6);
  //: Eased only for a zoom asked for by a press (a button, a key, a double
  //: click, a turn); a wheel, a pinch and a drag follow the hand directly.
  let glideTimer = 0;
  const glide = () => {
    if (reducedMotion()) return;
    const target = zoomTarget();
    target.classList.add("lightbox-glide");
    clearTimeout(glideTimer);
    glideTimer = setTimeout(() => target.classList.remove("lightbox-glide"), 260);
  };
  // A single image is the usual target; a PDF shown as pages (pdfPages,
  // below) is a second one, added when PDFs stopped being AI-text-only, 
  // "or zoom. a lot of controls are missing," reported live once pages
  // started rendering. Same zoom state and the same three buttons drive
  // both; only which element the transform lands on, and which container's
  // scroll resets on "Fit", differ.
  const zoomTarget = () => (!pdfPages.classList.contains("hidden") ? pdfPages : img);
  const scrollTarget = () => (!pdfPages.classList.contains("hidden") ? doc : stage);
  const applyZoom = () => {
    const target = zoomTarget();
    const isImg = target === img;
    if (zoom === 1) panX = panY = 0;
    //: The other of the two keeps no zoom of its own: paging from a zoomed
    //: PDF to a picture reset the picture only, and the page column came
    //: back at the old scale (with the zoom reading 100%) on the next PDF.
    const other = isImg ? pdfPages : img;
    if (other.style.transform) other.style.transform = "";
    other.classList.remove("zoomed");
    if (isImg) {
      //: Scaled from the top left (see the CSS), turned about the middle of
      //: the picture's own box, so `setZoom`'s anchor arithmetic is the same
      //: at every turn.
      const parts = [];
      if (zoom !== 1) parts.push(`translate(${panX}px, ${panY}px) scale(${zoom})`);
      if (rotation % 360) {
        const cx = img.offsetWidth / 2;
        const cy = img.offsetHeight / 2;
        parts.push(`translate(${cx}px, ${cy}px) rotate(${rotation}deg) scale(${turnFit()}) translate(${-cx}px, ${-cy}px)`);
      }
      target.style.transform = parts.join(" ");
    } else {
      target.style.transform = zoom === 1 ? "" : `scale(${zoom})`;
    }
    stage.classList.toggle("zoomed-img", isImg && zoom > 1);
    // Set on the stage too, a multi-page column has no single element
    // whose own hover state would otherwise flip the grab cursor.
    target.classList.toggle("zoomed", zoom > 1);
    stage.classList.toggle("zoomed", zoom > 1);
    //: A picture's readout is against its own pixels, as every viewer's is:
    //: "53%" at Fit for a picture twice the window, "100%" at actual size.
    const pixels = isImg && img.naturalWidth && img.offsetWidth;
    zoomLabel.textContent = `${Math.round((pixels ? zoom / actualZoom() : zoom) * 100)}%`;
    fitBtn.setAttribute("aria-pressed", String(zoom === 1));
    //: Pressed when the picture is already at actual size, so a press that
    //: changes nothing (a picture smaller than the window, where fit is 1:1)
    //: says why (owner 2026-10-19: "is that ratio button meant to do anything").
    actualBtn.setAttribute("aria-pressed", String(Math.abs(zoom - actualZoom()) < 0.01));
    // Only grab-able once there is something to pan to.
    //: **Only when it is not already there** (INBOX 424f). `show()` sets the
    //: zoom back to fit for every picture, so paging through a gallery called
    //: `scrollTo` on every press, and a `scrollTo` against a stage whose
    //: picture was just swapped is a forced layout: measured at 4x CPU, 375ms
    //: of five next/previous presses, for a stage that was already at its
    //: origin. `scrolledAway` is kept by the scroll listeners below, so the
    //: question costs no layout read.
    if (zoom === 1) {
      const scroller = scrollTarget();
      if (scrolledAway.has(scroller)) {
        scroller.scrollTo({ left: 0, top: 0 });
        scrolledAway.delete(scroller);
      }
    }
  };
  //: Which of the two scrollers is somewhere other than its top-left corner,
  //: from their own scroll events (a pan, a scrollbar, a wheel, the browser
  //: clamping after the content changed), read when the event fires, when
  //: layout is already clean.
  const scrolledAway = new WeakSet();
  const trackScrolledAway = (el) => {
    el.addEventListener(
      "scroll",
      () => {
        if (el.scrollLeft || el.scrollTop) scrolledAway.add(el);
        else scrolledAway.delete(el);
      },
      { passive: true }
    );
  };
  trackScrolledAway(stage);
  //: **Zoom where you are looking** (the owner: "I cant zoom in on specific
  //: parts only the top left of the attachment or image"). The scale's origin
  //: is the top left (so the overflow stays scrollable, see the CSS), which
  //: left every zoom anchored there. `anchor` is a viewport point, the
  //: pointer for a wheel or pinch or double-click, the stage's centre for the
  //: buttons: the fraction of the picture under it is measured before the
  //: scale and scrolled back under it after. Two rect reads per zoom step, on
  //: a user action, never per frame.
  //: A picture is panned by a translate, not by scrolling: a scroll area
  //: cannot reach overflow past its start edge, so every anchor near a
  //: small picture's left or top was clamped and the zoom drifted to the
  //: top left (measured: 70% across landed at 56%). Translate has no such
  //: edge. The PDF column keeps its scroll, which it needs for its pages.
  const setZoom = (next, anchor = null) => {
    const target = zoomTarget();
    const scroller = scrollTarget();
    const before = target.getBoundingClientRect();
    const box = scroller.getBoundingClientRect();
    const [ax, ay] = anchor || [box.left + box.width / 2, box.top + box.height / 2];
    const fx = before.width ? (ax - before.left) / before.width : 0.5;
    const fy = before.height ? (ay - before.top) / before.height : 0.5;
    const from = zoom;
    zoom = Math.min(zoomMax(), Math.max(ZOOM_MIN, Math.round(next * 1000) / 1000));
    if (target === img) {
      //: The transform's origin on screen: the picture's layout corner plus
      //: the pan. Not the bounding box's corner, which a turn moves.
      const ox = box.left + img.offsetLeft - stage.scrollLeft + panX;
      const oy = box.top + img.offsetTop - stage.scrollTop + panY;
      panX += (ax - ox) * (1 - zoom / from);
      panY += (ay - oy) * (1 - zoom / from);
      applyZoom();
      return;
    }
    applyZoom();
    if (zoom === 1) return;
    const after = target.getBoundingClientRect();
    scroller.scrollLeft += after.left + fx * after.width - ax;
    scroller.scrollTop += after.top + fy * after.height - ay;
  };
  //: `where` is the bar a control lives in: the document's own row under the
  //: page (the default), the top bar, or a zone of the view dock. An
  //: icon-only control takes its title as its name.
  const actionBtn = (label, title, fn, where = actions) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small lightbox-action";
    b.title = title;
    setLabel(b, label);
    if (!b.querySelector(".ph-text") && b.textContent.trim().length <= 1) {
      b.classList.add("icon-only");
      b.setAttribute("aria-label", title.replace(/ \([^)]*\)$/, ""));
    }
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      fn(b);
    });
    where.appendChild(b);
    return b;
  };
  const zoomBy = (factor) => {
    glide();
    setZoom(zoom * factor);
  };
  const fitView = () => {
    glide();
    setZoom(1);
  };
  const actualSize = () => {
    glide();
    setZoom(zoomTarget() === img ? actualZoom() : 1);
  };
  const turn = () => {
    if (zoomTarget() !== img) return;
    glide();
    rotation += 90;
    setZoom(1);
    applyZoom();
  };

  const dockPrevBtn = actionBtn("ph:caret-left", "Previous (Left arrow)", () => show(index - 1), dockPrevZone);
  const zoomOutBtn = actionBtn("ph:magnifying-glass-minus", "Zoom out (-)", () => zoomBy(1 / 1.5), dockZoomZone);
  dockZoomZone.appendChild(zoomLabel);
  const zoomInBtn = actionBtn("ph:magnifying-glass-plus", "Zoom in (+)", () => zoomBy(1.5), dockZoomZone);
  const resetBtn = actionBtn("ph:arrows-in", "Back to fit (0)", fitView, dockViewZone);
  const fitBtn = resetBtn;
  const actualBtn = actionBtn("1:1", "Actual size (1)", actualSize, dockViewZone);
  actualBtn.setAttribute("aria-label", "Actual size");
  const rotateBtn = actionBtn("ph:arrow-clockwise", "Rotate (R)", turn, dockViewZone);
  const dockNextBtn = actionBtn("ph:caret-right", "Next (Right arrow)", () => show(index + 1), dockNextZone);
  for (const b of [dockPrevBtn, dockNextBtn]) b.classList.add("lightbox-dock-nav");

  //: **The page stepper**: Phase 7.1's "a way to say which page you are on".
  //:
  //: The pages column already scrolls, and scrolling is the right way to read
  //: a document; what it could not do is *name* the page under your eye, which
  //: is the one fact everything else here hangs off, the read/unread chip that
  //: is current, and which page "open the reader here" opens. So this is a
  //: readout with two buttons, not a pager that replaces scrolling: both
  //: directions still work and they stay in sync (the scroll listener wired in
  //: `wireDocPageTracking` below writes the label back).
  //:
  //: Built here rather than further down because `actionBtn` appends in
  //: creation order and "where you are" belongs beside the zoom controls,
  //: which are the other thing that answers "what am I looking at".
  let docPageCount = 0;
  let docPage = 0;
  const docPagesRead = new Set();
  //: page index -> `{text, model, caption, caption_model}`, from the same
  //: `page-reads` response the chips are built from. **Per page** is the whole
  //: point (Phase 7.3): one caption under a whole PDF describes none of its
  //: pages, and the joined reading of every page is not what you are looking
  //: at when page 4 is on screen.
  const docPageRows = new Map();
  const pagePrevBtn = actionBtn("ph:caret-up", "Previous page", () => setDocPage(docPage - 1), dockPageZone);
  const pageLabel = document.createElement("span");
  pageLabel.className = "lightbox-page-label";
  //: `role="status"`, matching the OCR workspace's own page label: the page
  //: changes without focus moving, so a screen reader is otherwise never told.
  pageLabel.setAttribute("role", "status");
  dockPageZone.appendChild(pageLabel);
  const pageNextBtn = actionBtn("ph:caret-down", "Next page", () => setDocPage(docPage + 1), dockPageZone);
  const pageControls = [pagePrevBtn, pageLabel, pageNextBtn];
  const showPageControls = (on) =>
    pageControls.forEach((el) => el.classList.toggle("hidden", !on));
  showPageControls(false);

  //: Whichever box actually scrolls the pages. In the plain document view that
  //: is `.lightbox-doc`; once the reading is showing beside the pages
  //: (`lightbox-doc-split`) the pages column becomes its own scroller. Asking
  //: the DOM rather than tracking the mode: the split is toggled in three
  //: places and a fourth would silently scroll the wrong box.
  const pageScroller = () =>
    pdfPages.scrollHeight > pdfPages.clientHeight + 1 ? pdfPages : doc;

  function syncPageChips() {
    for (const chip of infoPages.querySelectorAll(".lightbox-page-chip")) {
      chip.classList.toggle("is-current", Number(chip.dataset.page) === docPage);
      chip.setAttribute("aria-current", Number(chip.dataset.page) === docPage ? "true" : "false");
    }
    pageLabel.textContent = docPageCount ? `Page ${docPage + 1} of ${docPageCount}` : "";
    pagePrevBtn.disabled = docPage <= 0;
    pageNextBtn.disabled = docPage >= docPageCount - 1;
    //: The panel below is about *this* page, its reading, its figures, so
    //: it is redrawn with the number, not only when the file changes.
    if (lightboxInfoItem) renderInfo(lightboxInfoItem, true);
    //: The workspace button opens at the page named here, so it has to say so
    //:, a button whose behaviour depends on invisible state is the affordance
    //: problem this app keeps fixing elsewhere.
    readWithAiBtn.title = docPageCount
      ? `Open the page reader at page ${docPage + 1}: the page beside what it says`
      : "Open the page reader: see each page beside what it says";
  }

  //: Set the current page *and* scroll to it. `setDocPage` is the user asking
  //: for a page; `noteDocPage` (below) is the scroll position telling us which
  //: one arrived: they must not call each other, or a scroll would fight the
  //: scroll it triggered.
  function setDocPage(next) {
    if (!docPageCount) return;
    docPage = Math.max(0, Math.min(docPageCount - 1, next));
    const target = pdfPages.children[docPage];
    if (target) {
      const scroller = pageScroller();
      //: Rects rather than `offsetTop`: `offsetTop` is measured against the
      //: nearest *positioned* ancestor, which is not the scroller in either
      //: of the two layouts this has to work in.
      scroller.scrollTop += target.getBoundingClientRect().top
        - scroller.getBoundingClientRect().top;
    }
    syncPageChips();
  }

  //: One chip per page, marked with whether that page has a stored reading.
  //: This is Phase 7.1's "which pages have been read", and it is deliberately
  //: the same `.chip` recipe the rest of the app uses rather than a bespoke
  //: badge: a page is a thing you can pick, which is what a chip is for.
  function renderDocPages() {
    infoPages.replaceChildren();
    infoPages.classList.toggle("hidden", docPageCount < 1);
    if (docPageCount < 1) return;
    const lead = document.createElement("span");
    lead.className = "muted text-sm lightbox-pages-lead";
    lead.textContent = docPagesRead.size
      ? `${docPagesRead.size} of ${docPageCount} pages read`
      : `${docPageCount} page${docPageCount === 1 ? "" : "s"} · none read yet`;
    infoPages.appendChild(lead);
    for (let i = 0; i < docPageCount; i++) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip chip-interactive lightbox-page-chip";
      chip.classList.toggle("is-read", docPagesRead.has(i));
      chip.dataset.page = String(i);
      chipWords(chip, String(i + 1));
      //: The number alone is not a label, "3" tells a screen reader nothing
      //: about what it is or what pressing it does.
      chip.setAttribute(
        "aria-label",
        docPagesRead.has(i) ? `Page ${i + 1}, already read` : `Page ${i + 1}, not read yet`
      );
      chip.title = chip.getAttribute("aria-label");
      chip.addEventListener("click", (e) => {
        e.stopPropagation();
        setDocPage(i);
      });
      infoPages.appendChild(chip);
    }
    syncPageChips();
  }

  //: Back to "this is not a document", called wherever the lightbox changes
  //: what it is showing, so a photograph never inherits the previous file's
  //: page count and a stale stepper never offers page 7 of an image.
  function resetDocPages() {
    docPageCount = 0;
    docPage = 0;
    docPagesRead.clear();
    docPageRows.clear();
    showPageControls(false);
    infoPages.replaceChildren();
    infoPages.classList.add("hidden");
  }

  //: Which pages already have a stored reading (`PageRead`, see the model's
  //: own docstring). Best-effort and never throws: the pages themselves render
  //: with no AI in the loop at all, and this panel must not be the thing that
  //: makes a document unviewable when the store cannot answer.
  async function loadDocPageReads(attachmentId, name, item) {
    let base = attachmentId ? `/files/${attachmentId}` : "";
    if (!base) {
      //: A `/media/` upload is addressed by *id* here and by *stored name*
      //: everywhere else in this function. The Library gallery is the one
      //: caller that already holds the id; every other one has a url, so the
      //: id is looked up the same way `hydrate` looks up the rest of the
      //: metadata rather than leaving the panel empty for eight of nine
      //: callers.
      let id = item.id;
      if (!id && name) {
        const row = await apiJson(`/media/meta/${encodeURIComponent(name)}`).catch(() => null);
        id = row?.id;
      }
      if (!id) return;
      //: Now that the id is known the workspace can be addressed too, the
      //: same button previously fell back to the flat inline reading for
      //: exactly this case.
      if (!lightboxOcrTarget) {
        lightboxOcrTarget = {
          id,
          _isAttachment: false,
          original_name: item.filename || name,
          //: See the note beside the other place this target is built: the
          //: page images are addressed by stored name, so leaving `url` off
          //: opens the workspace on a stage that 404s.
          url: `/media/${name}`,
        };
      }
      base = `/media/${id}`;
    }
    const body = await apiJson(`${base}/page-reads`).catch(() => null);
    for (const page of body?.pages || []) {
      const index = Number(page.page) || 0;
      if ((page.text || "").trim()) docPagesRead.add(index);
      docPageRows.set(index, {
        text: (page.text || "").trim(),
        model: page.model || "",
        caption: (page.caption || "").trim(),
        caption_model: page.caption_model || "",
      });
    }
    renderDocPages();
    //: The facts line carries the same count, so it has to be redrawn with the
    //: chips or the panel says "none read yet" above a row of read pages.
    renderInfo(item, true);
  }

  function noteDocPage() {
    if (!docPageCount) return;
    const scroller = pageScroller();
    const top = scroller.getBoundingClientRect().top;
    let nearest = 0;
    let best = Infinity;
    for (let i = 0; i < pdfPages.children.length; i++) {
      //: The page whose top edge is closest to the top of the viewport, from
      //: either side: a page scrolled half off the top is still the page you
      //: are reading, so `Math.abs` rather than "the first one still below".
      const distance = Math.abs(pdfPages.children[i].getBoundingClientRect().top - top);
      if (distance < best) {
        best = distance;
        nearest = i;
      }
    }
    if (nearest === docPage) return;
    docPage = nearest;
    syncPageChips();
  }
  //: **"Open this in the editor", from the preview.** Asked for directly: "add
  //: an edit document button to previewed documents in the lightbox." The
  //: Library's own kebab offers Preview *and* Open, but once you are in the
  //: preview and have decided you want to change something, the only route
  //: back was to close the lightbox, find the row again and pick the other
  //: menu item: three steps to answer a question the preview itself raised.
  //:
  //: Only for a *document*: the lightbox also shows attachments and uploaded
  //: files, which have their own in-place edit (`editFileBtn`) and no row in
  //: the Documents tab to open. `item.documentId` is what says which is which,
  //: set by the one caller that previews a document.
  const openDocBtn = actionBtn("ph:pencil-simple Edit document", "Open this in the document editor", () => {
    const target = items[index];
    if (!target || !target.documentId) return;
    close();
    switchTab("documents");
    openDocument(target.documentId);
  });
  openDocBtn.classList.add("hidden");
  // Zoom is an image control. A document scrolls and reflows instead, so
  // showing a disabled-in-spirit 100% beside a page of text is three
  // controls that do nothing, the same "only show what this can do"
  // reasoning the whiteboard context menu already settled.
  //: Actual size and Rotate are a picture's: a page column has no single
  //: pixel size, and turning a document is not reading it.
  const zoomControls = [zoomOutBtn, zoomLabel, zoomInBtn, resetBtn];
  const showZoomControls = (on) => {
    zoomControls.forEach((el) => el.classList.toggle("hidden", !on));
    const picture = on && pdfPages.classList.contains("hidden");
    actualBtn.classList.toggle("hidden", !picture);
    rotateBtn.classList.toggle("hidden", !picture);
  };

  // Wheel-to-zoom, because that is what every image viewer does and a person
  // who has zoomed once will try it. Non-passive so the page behind cannot
  // scroll out from under the picture mid-zoom.
  //
  // **Only while an image is actually showing.** Reported live, from a real
  // multi-page PDF: "it crashed when I tried to view a pdf and i couldnt
  // scroll." Not a crash: `stage` is the shared container for both the
  // picture view and `.lightbox-doc` (text, and now PDF pages), and this
  // handler used to call `preventDefault()` on every wheel event over it
  // unconditionally, regardless of which one was showing. Over a scrolling
  // multi-page PDF that blocked the browser's own scroll on every tick
  // while doing nothing visible in return, `setZoom` only ever touches the
  // single `<img>` element's transform, which isn't part of the document
  // view at all. `doc.classList.contains("hidden")` is the same check
  // `show()` already uses to know which of the two is current.
  stage.addEventListener(
    "wheel",
    (e) => {
      // A browser reports a trackpad pinch gesture as a wheel event with
      // ctrlKey set: the same convention Chrome/Firefox use for
      // Maps/Docs/Figma-style pinch-to-zoom: so it still reaches zoom even
      // while the document view owns plain scroll below. Plain wheel/two-
      // finger scroll over a document (not pinch) is left alone entirely.
      if (!doc.classList.contains("hidden") && !e.ctrlKey) return;
      if (!doc.classList.contains("hidden") && pdfPages.classList.contains("hidden")) return; // plain text: nothing to zoom
      e.preventDefault();
      //: In proportion to the travel, so a trackpad's many small deltas and
      //: a wheel's one notch of 100 both feel continuous (a notch: x1.22).
      //: A line or a page of travel (`deltaMode` 1, 2) counts as 40px.
      const travel = Math.max(-200, Math.min(200, e.deltaY * (e.deltaMode ? 40 : 1)));
      setZoom(zoom * Math.exp(-travel * 0.002), [e.clientX, e.clientY]);
    },
    { passive: false }
  );
  //: Double-click zooms into the spot clicked, and back out to fit: the
  //: gesture every image viewer has, and the quickest way to "zoom in on
  //: specific parts".
  stage.addEventListener("dblclick", (e) => {
    if (!doc.classList.contains("hidden") && pdfPages.classList.contains("hidden")) return;
    e.preventDefault();
    //: Fit and actual size, the two views a person flips between; a picture
    //: already shown at its own size (or a page column) goes to twice.
    const near = zoomTarget() === img ? actualZoom() : 2;
    glide();
    setZoom(zoom > 1 ? 1 : near > 1.05 ? near : 2, [e.clientX, e.clientY]);
  });

  // Drag to pan, once zoomed. The scrollbars already pan the stage, but a
  // magnified picture with `cursor: grab` on it that does not actually drag
  // is an affordance telling a lie, every image viewer drags here.
  //
  // Bound to both `img` and `pdfPages`, panning whichever container
  // `scrollTarget()` says actually scrolls (`stage` for the image, `doc`
  // for PDF pages): reported live: "when zooming in on docs or images etc
  // in the lightbox, i cant drag to adjust the zoom position." This only
  // ever panned `stage.scroll{Left,Top}` via listeners on `img` alone, the
  // same single-target gap `zoomTarget()`/`scrollTarget()` above already
  // exist to close for zoom and Fit; drag never got the same treatment when
  // PDF pages gained their own zoomable, independently-scrolling view.
  let panning = null;
  const startPan = (el) => (e) => {
    if (zoom === 1) return;
    e.preventDefault();
    el.classList.remove("lightbox-glide");
    const scroller = scrollTarget();
    panning = { x: e.clientX, y: e.clientY, left: scroller.scrollLeft, top: scroller.scrollTop, px: panX, py: panY };
    el.setPointerCapture(e.pointerId);
    el.style.cursor = "grabbing";
  };
  const movePan = (e) => {
    if (!panning) return;
    if (zoomTarget() === img) {
      panX = panning.px + (e.clientX - panning.x);
      panY = panning.py + (e.clientY - panning.y);
      applyZoom();
      return;
    }
    const scroller = scrollTarget();
    scroller.scrollLeft = panning.left - (e.clientX - panning.x);
    scroller.scrollTop = panning.top - (e.clientY - panning.y);
    //: Now, not at the scroll event a frame later: a Fit pressed inside that
    //: frame must still see the pan.
    scrolledAway.add(scroller);
  };
  const endPan = (el) => (e) => {
    if (!panning) return;
    panning = null;
    el.style.cursor = "";
    if (e.pointerId !== undefined && el.hasPointerCapture(e.pointerId)) {
      el.releasePointerCapture(e.pointerId);
    }
  };
  // A drag that ends on the picture must not also read as a click on the
  // backdrop, which closes the dialog, panning to the edge of a picture
  // and having the whole thing vanish is the bug this prevents.
  //
  // `pdfPages` doesn't exist yet at this point in `openLightbox` (it's
  // built further down, alongside the rest of the document view), wiring
  // it up here throws a temporal-dead-zone ReferenceError the instant the
  // lightbox opens. `bindPan`, called once `pdfPages` is actually in scope.
  const bindPan = (el) => {
    el.addEventListener("pointerdown", startPan(el));
    el.addEventListener("pointermove", movePan);
    el.addEventListener("pointerup", endPan(el));
    el.addEventListener("pointercancel", endPan(el));
    el.addEventListener("click", (e) => e.stopPropagation());
  };
  bindPan(img);
  //: **A finger's gestures on the picture**: two pinch about their midpoint,
  //: one swiped sideways at Fit moves to the next or previous file. Measured
  //: before at 390: a swipe and a pinch both left the view as it was. The
  //: picture takes `touch-action: none` (lightbox-lazy.css), so the browser
  //: hands these over instead of scrolling the dialog.
  const fingers = new Map();
  let pinch = null;
  let swipe = null;
  const spread = () => {
    const [a, b] = [...fingers.values()];
    return { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, mid: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] };
  };
  img.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse") return;
    fingers.set(e.pointerId, [e.clientX, e.clientY]);
    if (fingers.size === 2) {
      panning = null;
      swipe = null;
      pinch = { d: spread().d, z: zoom };
    } else if (fingers.size === 1 && zoom === 1) {
      swipe = { x: e.clientX, y: e.clientY };
    }
  });
  img.addEventListener("pointermove", (e) => {
    if (!fingers.has(e.pointerId)) return;
    fingers.set(e.pointerId, [e.clientX, e.clientY]);
    if (pinch && fingers.size === 2) {
      const now = spread();
      setZoom(pinch.z * (now.d / pinch.d), now.mid);
    }
  });
  const liftFinger = (e) => {
    if (!fingers.has(e.pointerId)) return;
    fingers.delete(e.pointerId);
    if (fingers.size < 2) pinch = null;
    if (!swipe || fingers.size || e.type === "pointercancel") return;
    const dx = e.clientX - swipe.x;
    const dy = e.clientY - swipe.y;
    swipe = null;
    if (items.length > 1 && zoom === 1 && Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      show(index + (dx < 0 ? 1 : -1));
    }
  };
  img.addEventListener("pointerup", liftFinger);
  img.addEventListener("pointercancel", liftFinger);

  // Copy the text the app read out of the picture. Hidden unless this item
  // actually has some: an enabled button that copies "" is a lie.
  // Goes through the app's own `copyToClipboard` helper rather than the raw
  // browser clipboard call: caught by
  // test_every_copy_path_goes_through_the_fallback (whose naive string scan
  // would otherwise flag even *this comment* if it spelled the call out
  // literally, which is why it doesn't). The helper already covers what a
  // hand-rolled version here did not: a non-secure context, permission
  // refused, and a last-resort "here's the text, already selected" UI when
  // both fail, instead of this button just going silent.
  //: What the info panel is currently showing, which for a document is *one
  //: page's* reading rather than the file's joined one (see `renderInfo`).
  //: Copy has to hand over what is on screen: copying every page while the
  //: panel shows page 4 is the app disagreeing with itself about "this text".
  let lightboxShownText = "";
  const copyBtn = actionBtn("ph:copy", "Copy the text read from this image", async (b) => {
    const value = (lightboxShownText || items[index].text || "").trim();
    if (!value) return;
    await copyToClipboard(value, b);
  }, topActions);

  // Save the original file. `download` needs a same-origin href to name the
  // file, which `mediaSrc()` gives us: it is this app's own /media route.
  actionBtn("ph:download-simple", "Download this file", async () => {
    try {
      const current = items[index];
      const href = await current.getUrl();
      const a = document.createElement("a");
      a.href = href;
      // **A document leaves `download` unset, an image sets it.** A
      // non-empty `download` attribute wins over the server's own
      // `Content-Disposition: filename="..."`, for
      // `/documents/{id}/export.md`, that header already carries the
      // right extension for the file's actual type (`.py`, `.json`,
      // `.md`, whatever `filetypes.get` picked), computed server-side.
      // Setting `download` to a bare title here would have downloaded a
      // "Quarterly Report" with no extension at all, silently discarding
      // that work: an image has no such header to defer to, so it keeps
      // naming itself.
      if (!current.kind) a.download = current.filename || "image";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch {
      toast("Couldn't save that file.", true);
    }
  }, topActions);
  //: "Open in": the browser's own viewer, in a tab of its own, for a file
  //: with a url (a native document has none: its url is a download).
  const openTabBtn = actionBtn("ph:arrow-square-out", "Open in a new tab", async () => {
    const item = items[index];
    let href = item.openUrl || (await Promise.resolve(item.getUrl()).catch(() => ""));
    if (!href) return;
    //: The desktop window opens a tab in the system browser, which has no
    //: media cookie ("The app is locked", the owner, 2026-10-27): a two-minute
    //: link to this one file goes instead (`/auth/media-link`).
    const path = new URL(href, location.href);
    if (path.origin === location.origin && /^\/(media|files)\//.test(path.pathname) && (await desktopShell())) {
      const link = await apiJson("/auth/media-link", { method: "POST", body: JSON.stringify({ path: path.pathname }) }).catch(() => null);
      if (!link) return toast("Couldn't open that in a tab.", true);
      href = link.url + path.search.replace(/^\?/, "&");
    }
    window.open(href, "_blank", "noopener");
  }, topActions);
  openTabBtn.classList.add("lightbox-open-tab");
  //: The details under the picture (facts, caption, reading) can be put
  //: away for a clear view, and stay put away for the next picture.
  let infoWanted = prefs.get("lightboxInfo", "on") !== "off";
  const infoBtn = actionBtn("ph:info", "Details (I)", () => {
    infoWanted = !infoWanted;
    prefs.set("lightboxInfo", infoWanted ? "on" : "off");
    syncInfoWanted();
  }, topActions);
  const syncInfoWanted = () => {
    info.classList.toggle("lightbox-info-off", !infoWanted);
    infoBtn.setAttribute("aria-pressed", String(infoWanted));
    infoBtn.classList.toggle("hidden", info.classList.contains("hidden"));
  };
  //: The '?' (the `data-help-for` recipe): what the pointer, the keys and a
  //: finger do here, none of which a button can show.
  const helpBtn = actionBtn("ph:question", "About the viewer", () => {}, topActions);
  helpBtn.setAttribute("data-help-for", "lightbox-help");
  helpBtn.setAttribute("aria-controls", "lightbox-help");
  helpBtn.setAttribute("aria-expanded", "false");
  helpBtn.classList.add("lightbox-help-btn");
  const helpBody = document.createElement("div");
  helpBody.className = "help-body hidden";
  helpBody.id = "lightbox-help";
  helpBody.setAttribute("role", "dialog");
  helpBody.setAttribute("aria-label", "About the viewer");
  for (const line of LIGHTBOX_HELP) {
    const p = document.createElement("p");
    p.textContent = line;
    helpBody.appendChild(p);
  }
  topActions.append(helpBody, closeBtn);
  wireHelpPopover(helpBtn, helpBody);

  // Only shown while a PDF is displayed as pages (see showDocument): swaps
  // to the AI-extracted-text view on demand, rather than automatically. A
  // PDF's *pages* render with zero AI involvement; reading its words with a
  // model is a deliberate, opt-in second step, not something a user has to
  // sit through just to look at their own document.
  //: **Which PDF the OCR workspace should open, or null.** Set by
  //: `showDocument`'s PDF branch, where the file's identity is actually
  //: known; cleared wherever the lightbox resets for a new file.
  let lightboxOcrTarget = null;

  const readWithAiBtn = actionBtn("ph:sparkle Read text with AI", "Open the page reader: see each page beside what it says", () => {
    //: **One reader, not two.** Reported: *"that panel is separate from the
    //: lightbox where you can select to read the text on the document, and I
    //: feel like that button should show the other text on page panel
    //: popup."* This button used to swap the lightbox to a flat blob of
    //: extracted text, while the OCR workspace, page rail, region boxes,
    //: per-page and now per-range reads, copy, save as note, was a separate
    //: window reachable only from a file card's menu. Two answers to "what
    //: does this document say", and the worse one was on the file you were
    //: looking at.
    //:
    //: Falls back to the old inline text when the workspace cannot be
    //: addressed (no id resolved, or library.js absent on this surface):
    //: degrading to the flat reading beats a button that does nothing.
    //: **At the page you are looking at, not at page 1.** Phase 7.1 asked for
    //: "a way into the OCR Workspace at that page", and the third argument is
    //: it: a fifteen-page scan opened at its first page from page nine is a
    //: navigation the reader has to redo by hand, every time.
    if (lightboxOcrTarget && typeof window.openOcrWorkspace === "function") {
      //: **The lightbox goes before the workspace arrives.** Reported: *"when
      //: I open a pdf file in the lightbox and press the read text with ai, it
      //: opens the ocr workspace but behind the lightbox so the lightbox needs
      //: to close when the workspace opens."* Measured: `.lightbox` is
      //: `z-index: 1020` (raised there to clear the CSS full-screen graph, see
      //: its own comment) and the workspace is a `.modal-overlay` at 1010, so
      //: the workspace really did open underneath and every click landed on
      //: the lightbox's zoom-out backdrop instead. The fix is the one the
      //: gallery kebab's "See text on the page" row already uses ten lines
      //: down, `close()` first: two stacked overlays leave the page behind
      //: unreachable whichever of them wins the stacking contest, so raising
      //: the workspace above the lightbox would answer the z-index and not the
      //: report. The target and the page are read into locals before the
      //: dismiss because `close()` empties the lightbox's own state.
      const target = lightboxOcrTarget;
      const atPage = docPageCount ? docPage : 0;
      close();
      window.openOcrWorkspace(target, [], atPage);
      return;
    }
    lightboxLoadExtractedText?.();
  });
  readWithAiBtn.classList.add("hidden");

  //: **Edit / Save / Cancel for a text file**, §R7.1 item 2. Set by
  //: `showDocument` for whichever file is open; null while the lightbox is
  //: showing a picture or a PDF's pages, which is what keeps these three
  //: buttons from acting on the file that happened to be open before.
  let lightboxEditTarget = null;

  function setLightboxEditing(on) {
    docEdit.classList.toggle("hidden", !on);
    docBody.classList.toggle("hidden", on);
    //: Find-in-document searches the *rendered* body, so it has nothing to
    //: work on while the source is showing, and leaving it up would offer a
    //: search that silently matches nothing.
    find.classList.toggle("hidden", on);
    findCount.classList.add("hidden");
    editFileBtn.classList.toggle("hidden", on);
    saveFileBtn.classList.toggle("hidden", !on);
    cancelEditBtn.classList.toggle("hidden", !on);
    //: Export hands back what was *saved*; while a draft is open in the box
    //: the two disagree, and a file exported mid-edit would silently be the
    //: version before the changes on screen.
    if (on) exportTextBtn.classList.add("hidden");
    else if (lightboxExtractedText) exportTextBtn.classList.remove("hidden");
    if (on) docEdit.focus();
  }

  const editFileBtn = actionBtn("ph:pencil-simple Edit", "Edit this file's text", () => {
    if (!lightboxEditTarget) return;
    docEdit.value = lightboxEditTarget.text;
    setLightboxEditing(true);
  });
  editFileBtn.classList.add("hidden");

  const saveFileBtn = actionBtn("ph:check Save changes", "Save this text back over the file", async (button) => {
    if (!lightboxEditTarget) return;
    button.disabled = true;
    try {
      const wasText = lightboxEditTarget.text;
      const saved = await apiJson(lightboxEditTarget.url, {
        method: "PUT",
        body: JSON.stringify({ text: docEdit.value }),
      });
      pushRequestUndo("Edited a file's text", lightboxEditTarget.url, "PUT", { text: wasText }, { text: saved.text ?? docEdit.value }, () => lightboxLoadExtractedText?.());
      //: Re-rendered from what the server wrote back, not from what was
      //: typed. They are the same today; if they ever differ, a normalised
      //: line ending, a file the OS rewrote, the reader should be looking at
      //: the file, not at the draft of it.
      lightboxEditTarget.text = saved.text || "";
      setLightboxEditing(false);
      lightboxLoadExtractedText?.();
      toast("Saved.");
    } catch (error) {
      //: A 409 is the server declining to overwrite (`docview.editability`),
      //: and its `detail` is written to be read by a person, so it is shown
      //: rather than replaced with a generic failure.
      toast(error.message || "Couldn't save that file.", true);
    } finally {
      button.disabled = false;
    }
  });
  saveFileBtn.classList.add("hidden");

  const cancelEditBtn = actionBtn("ph:x Cancel", "Discard these changes", () => {
    setLightboxEditing(false);
  });
  cancelEditBtn.classList.add("hidden");

  //: **Exporting the *text*, which is a different thing from Save** (§R7.1
  //: item 5, "export, per-format, from the same place the file is viewed").
  //: Save hands back the file as it is on disk, the .pdf, the .docx. This
  //: hands back what the viewer is showing, which for a scanned PDF or a Word
  //: file is the only readable form of it the app has, and until now could be
  //: reached only by selecting the whole pane and copying.
  //:
  //: The extension follows `kind`, not the source file's: markdown text saved
  //: as `report.pdf.md` is honest about being neither a PDF nor a plain
  //: transcript, and opens in the right thing.
  let lightboxExtractedText = null;
  const exportTextBtn = actionBtn("ph:export Export text", "Save the extracted text as a file", async (button) => {
    if (!lightboxExtractedText) return;
    button.disabled = true;
    try {
      const { name, kind, text } = lightboxExtractedText;
      const stem = (name || "document").replace(/\.[^./\\]+$/, "") || "document";
      const extension = kind === "markdown" ? "md" : "txt";
      await saveFile(`${stem}.${extension}`, new Blob([text], { type: "text/plain" }));
    } catch (error) {
      toast(error.message || "Couldn't export that text.", true);
    } finally {
      button.disabled = false;
    }
  });
  exportTextBtn.classList.add("hidden");

  //: Whether the preview frame is currently showing something.
  let docPreviewOn = false;

  function clearDocPreview() {
    docPreviewOn = false;
    docFrame.classList.add("hidden");
    //: `about:blank` rather than leaving the last file loaded: an iframe that
    //: still holds a document keeps rendering it, and paging to the next file
    //: would show the previous one's page for as long as the new fetch takes.
    docFrame.src = "about:blank";
    previewHtmlBtn.setAttribute("aria-pressed", "false");
    setLabel(previewHtmlBtn, "ph:browser Preview");
  }

  const previewHtmlBtn = actionBtn("ph:browser Preview", "Render this HTML file (scripts are not run)", () => {
    if (docPreviewOn) {
      clearDocPreview();
      docBody.classList.remove("hidden");
      find.classList.remove("hidden");
      return;
    }
    if (!lightboxPreviewSource) return;
    //: **A server URL, not a `blob:` from the text we already have.** The
    //: first version did the obvious thing and built a Blob, and a `blob:`
    //: document inherits its creator's CSP, so this app's `style-src 'self'`
    //: applied to the framed page and refused the page's *own* `<style>`
    //: block. Measured: "Refused to apply inline style", and a page setting
    //: `background:#eef` rendered transparent. `/files/{id}/html-preview`
    //: carries its own policy (`HTML_PREVIEW_CSP`, routes_files.py): 
    //: sandboxed, scriptless, and allowed to style itself.
    docFrame.src = mediaSrc(lightboxPreviewSource);
    docPreviewOn = true;
    docFrame.classList.remove("hidden");
    docBody.classList.add("hidden");
    //: Find-in-document reads the rendered *source* listing; the frame is a
    //: separate document this page deliberately cannot reach into.
    find.classList.add("hidden");
    findCount.classList.add("hidden");
    previewHtmlBtn.setAttribute("aria-pressed", "true");
    setLabel(previewHtmlBtn, "ph:code Show source");
  });
  previewHtmlBtn.classList.add("hidden");
  previewHtmlBtn.setAttribute("aria-pressed", "false");

  //: The URL the preview frame would load, set by `showDocument` only for a
  //: file that is actually HTML *and* is a real attachment (a `/media/`
  //: upload is never HTML, `MEDIA_SUFFIXES` is images and PDF, and a native
  //: document has no file behind it at all). Null the rest of the time, which
  //: is what keeps the button from framing the file viewed before this one.
  let lightboxPreviewSource = null;

  // **The AI/manage actions: gated on a media id, and only ever visible
  // when one is present.** Reported directly, and left open on purpose the
  // first time this bar was built: rename, describe with AI, read text (two
  // ways) and delete all need a real `MediaUpload` row, and of nine
  // `openLightbox` callers only the Library's own gallery has one to pass.
  // Every other caller (a note attachment, a chat image, a graph or
  // dashboard thumbnail, a whiteboard object) opens the lightbox from a bare
  // url, and a menu that 404s on click is worse than no menu, the same "two
  // buttons guaranteed to fail" shape this project already rejected once on
  // the whiteboard's own context menu.
  //
  // Reuses the endpoints and request shapes the gallery kebab already
  // established (library.js) rather than inventing a second idea of what
  // "describe with AI" does.
  let moreMenu = null;
  const buildMoreMenu = (item) => {
    //: **The job outlives the window that started it.**
    //:
    //: Reported: "if i close the lightbox as I am generating ocr, then it
    //: stops and I have to restart it again." The request never actually
    //: stopped: a `POST` keeps going and writes its result to the database
    //: whatever the browser does next, but every trace of it was inside the
    //: lightbox, so closing that window meant the work became invisible and
    //: then, on reopening, appeared not to have happened.
    //:
    //: Three changes make it true as well as visible: a progress toast that
    //: lives outside the lightbox, a re-render that is guarded rather than
    //: assumed (the panel may be gone by now, and writing to it threw), and a
    //: Library refresh so the gallery behind shows the new text either way.
    const run = (label, busyText, endpoint, applyTo) => async () => {
      const name = item.original_name || "this file";
      const progress = toastProgress(`${busyText} ${name}`);
      try {
        //: Registered with the OCR workspace's own in-flight map, so a read
        //: started here is still findable after this window closes, reported:
        //: "I close the lightbox, the ocr workspace is gone… it should be
        //: openable if an active ocr reading is going on."
        const updated = await (window.trackOcrRead || ((_i, _l, p) => p))(
          item,
          `${busyText} ${name}`,
          //: `force: true`, always. Reported: "the image captioning and ocr didnt
          //: work when I didnt like the output, deleted what was there and
          //: tried to do it again." A click on Describe / Read *is* the
          //: request to do it again, the server's "keep what exists" guard is
          //: for the automatic pass on upload, not for a person pressing the
          //: button a second time.
          apiJson(`/media/${item.id}${endpoint}`, { method: "POST", body: JSON.stringify({ force: true }) })
        );
        applyTo(item, updated);
        //: Only if this lightbox is still the one on screen. `renderInfo`
        //: writes into elements this closure captured, and they are detached
        //: once the overlay closes.
        if (overlay.isConnected && !overlay.classList.contains("hidden")) renderInfo(item, true);
        if (typeof loadLibrary === "function") loadLibrary();
        progress.done(`Finished reading ${name}.`, {
          actionLabel: "Show it",
          onAction: () => {
            switchTab("library");
            if (typeof renderLibrary === "function") renderLibrary();
          },
          go: { tab: "library" },
        });
      } catch (err) {
        progress.done(err.message || `Couldn't ${label.toLowerCase()}.`, { isError: true });
      }
    };
    const items = [
      {
        label: "ph:sparkle Describe with AI",
        title: "Generate a caption for this image",
        run: run("describe", "Describing…", "/caption", (it, u) => {
          it.caption = u.caption || "";
          it.captionByline = captionBylineFor(u);
        }),
      },
      {
        label: "ph:sparkle Read text with AI",
        title: "Read the text in this image with a vision model",
        //: The response carries both readings, so the panel is rebuilt from the
        //: whole row rather than from the field this call happened to write:
        //: re-reading with a model used to drop a Tesseract reading that was
        //: still stored, and running Tesseract used to promote it over a vision
        //: reading that is still the current one.
        run: run("read text", "Reading…", "/vision-ocr", (it, u) => {
          Object.assign(it, lightboxReadingsFor(u));
        }),
      },
    ];
    // "the whole application is offline anyway with local models so that
    // title is confusing" (reported directly): renamed to name the actual
    // method (Tesseract) instead of a property ("offline") every reading
    // path in this app already shares. And: "the option should be disabled
    // or hidden if the user doesn't have pytesseract installed", `/models/
    // status`'s `tesseract_available` (routes_models.py) is a plain
    // `shutil.which` check, so this can just not offer a button that would
    // otherwise silently do nothing, matching how the model-pull panel
    // already hides itself on a backend that can't pull.
    //: And now it is *left out* rather than shown greyed, which is the
    //: second half of the same report: "make sure all the fila and document
    //: ocr worfs with ai ocr models, I dont use tesseract." A disabled row
    //: that can never become enabled (this app never installs the binary, by
    //: instruction) is a permanent piece of dead chrome in a menu that opens
    //: on every image: and it sat directly under the row that does the same
    //: job with a model, which is the one the reader wants. INSTALL.md still
    //: documents the offline reader for anyone who wants it.
    if (!modelStatus || modelStatus.tesseract_available !== false) {
      items.push({
        label: "ph:scan Read text (Tesseract OCR)",
        title: "Read the text in this image with Tesseract, a fast local tool, no AI model involved",
        run: run("read text", "Reading…", "/ocr", (it, u) => {
          Object.assign(it, lightboxReadingsFor(u));
        }),
      });
    }
    //: The other door into the OCR workspace (library.js). The gallery's own
    //: kebab has it too, and this is the same act from the other surface: the
    //: lightbox is where you are *looking* at the page, which is exactly when
    //: "where did that line come from" gets asked. Gated on a media id like
    //: every other row here, and on the row being an image the extractor can
    //: open: a menu row guaranteed to 415 is worse than a shorter menu.
    //: PDFs included since the workspace learned to rasterise a page
    //: (`_pdf_regions_for`, routes_files.py): reported as *"is the document
    //: ocr even working??"*, and it was not: this gate is what kept every
    //: document out of the one window built to read documents.
    if (/\.(png|jpe?g|gif|webp|bmp|pdf)$/i.test(item.filename || "")) {
      items.push({
        label: "ph:selection-all See text on the page",
        title: "Open this file beside the text read from it, page by page",
        run: async () => {
          //: `close` is this lightbox's own dismiss (defined further down in
          //: `openLightbox`, hoisted and initialised long before any menu row
          //: can run). The workspace is a modal too, and two stacked overlays
          //: leave the page behind unreachable.
          close();
          //: `_src`, not `url`: the lightbox item already carries a resolved
          //: src (`getUrl` runs it through `mediaSrc`, which resolves a staged
          //: picture to its blob), so the workspace takes it as it is.
          window.openOcrWorkspace?.(
            {
              id: item.id,
              _src: item.getUrl ? item.getUrl() : "",
              original_name: item.filename,
              _isImage: !/\.pdf$/i.test(item.filename || ""),
            },
            [],
          );
        },
      });
    }
    const menu = kebabMenu(
      [
        ...items,
        {
          label: "ph:pencil-simple Rename",
          title: "Rename this image",
          run: async () => {
            const next = window.prompt("New name", item.filename || "");
            if (!next || !next.trim() || next === item.filename) return;
            try {
              const updated = await apiJson(`/media/${item.id}`, {
                method: "PUT",
                body: JSON.stringify({ original_name: next.trim() }),
              });
              pushRequestUndo("Renamed an image", `/media/${item.id}`, "PUT", { original_name: item.filename || "" }, { original_name: updated.original_name });
              item.filename = updated.original_name;
              renderInfo(item, true);
            } catch (err) {
              toast(err.message || "Couldn't rename that image.", true);
            }
          },
        },
        {
          label: "ph:trash Delete",
          title: "Delete this image",
          run: async () => {
            if (!(await confirmDialog(`Delete "${item.filename || "this image"}"?`))) return;
            try {
              const gone = await apiJson(`/media/${item.id}`, { method: "DELETE" });
              pushTokenUndo(`Deleted “${item.filename || "an image"}”`, [{ del: [`/media/${item.id}`, "DELETE"], restore: "/media/restore", token: gone.undo_token }], () => (typeof renderLibraryImagesGallery === "function" ? renderLibraryImagesGallery() : null));
              items.splice(index, 1);
              if (!items.length) {
                close();
                return;
              }
              show(index);
            } catch (err) {
              toast(err.message || "Couldn't delete that image.", true);
            }
          },
        },
      ],
      "More actions for this image"
    );
    //: The row's height, as Save and Find are (the owner, 2026-10-10: "These
    //: elements in the lightbox aren't the same height"; measured at 1440:
    //: this ⋯ 28px beside 32px). Inline: boot CSS is at its cap.
    const opener = menu.querySelector("button");
    opener.style.minHeight = opener.style.minWidth = "max(2rem, var(--target-min))";
    return menu;
  };
  const syncMoreMenu = (item) => {
    moreMenu?.remove();
    // `!item.kind` matters here, not just belt-and-braces: a native
    // document preview item (below) also carries `item.id`, but that id
    // names a *document*, not a media upload, feeding it to
    // `/media/{id}/caption` or `/media/{id}` DELETE would act on whatever
    // media row happens to share that number, or 404. This menu is media-
    // actions only; `item.kind` is how a document identifies itself.
    moreMenu = item.id && !item.kind ? buildMoreMenu(item) : null;
    if (moreMenu) topActions.insertBefore(moreMenu, closeBtn);
  };


  // **The document half of the showcase.** Asked for directly: the lightbox
  // should be "a sort of document preview… for viewing pdfs, word documents,
  // spreadsheets, text files, code files etc but in a presentable way that
  // isn't editable".
  //
  // Read-only is not a shortcut here, `/media/text` returns *extracted*
  // text, so what is on screen has already stopped being a .docx and there
  // is nothing coherent to write back into. `core/docview.py`'s own module
  // docstring makes the same point.
  const doc = document.createElement("div");
  doc.className = "lightbox-doc hidden";
  const docBody = document.createElement("div");
  docBody.className = "lightbox-doc-body";
  const docNote = document.createElement("p");
  docNote.className = "muted lightbox-doc-note hidden";
  // A PDF's actual pages, rasterised server-side, direct instruction, after
  // the AI-extraction path alone left a scanned PDF stuck on "Reading…"
  // forever: "pdfs and documents should be viewable, accessible and
  // manageable without the ai, even if the ai cant read them." Plain
  // <img>s, one per page, in their own scrolling column so a PDF scrolls
  // like a PDF: no script, no PDF renderer, no AI in this path at all.
  const pdfPages = document.createElement("div");
  pdfPages.className = "lightbox-pdf-pages hidden";
  bindPan(pdfPages);
  //: Bound here rather than beside `noteDocPage` itself, and for the same
  //: reason `bindPan` exists: `doc` and `pdfPages` are created further down
  //: this function, so touching either from the block that defines the page
  //: stepper is a temporal-dead-zone ReferenceError the instant the lightbox
  //: opens. Bound once each, never rebound per document, a listener added on
  //: every `showDocument` is the unbounded accumulation
  //: `test_frontend_handlers.py` exists to catch.
  //:
  //: Both boxes, because which one scrolls depends on the layout (see
  //: `pageScroller`), and `noteDocPage` is a no-op when there are no pages.
  doc.addEventListener("scroll", noteDocPage, { passive: true });
  pdfPages.addEventListener("scroll", noteDocPage, { passive: true });
  trackScrolledAway(doc);
  //: **Editing a file in place** (REDESIGN.md §R7.1 item 2, and the request:
  //: *"all the files should be managable, viewable and editable in the
  //: library and document/file/text editor"*). A plain textarea over the
  //: file's own text, and only ever for the files where that text *is* the
  //: file: `docview.editability` decides, server-side, and the route
  //: re-checks rather than trusting the flag it sent.
  const docEdit = document.createElement("textarea");
  docEdit.className = "lightbox-doc-edit hidden";
  docEdit.spellcheck = false;
  docEdit.setAttribute("aria-label", "Edit this file's text");
  //: **The HTML preview pane** (§R7.1 item 4, from the odysseus comparison:
  //: *"viewing html and other code"*). An .html file is the one type where
  //: the source and the thing it describes are both worth looking at, and
  //: showing only the source is showing half the file.
  //:
  //: `sandbox` with **no** `allow-` tokens, and that is the whole security
  //: story: no scripts, no forms, no same-origin, no top-level navigation.
  //: The page renders as layout and can do nothing else, which is what makes
  //: it safe to point at a file nobody in this notebook wrote. `core/security`
  //: allows `frame-src blob:` for this; the sandbox is what bounds it.
  const docFrame = document.createElement("iframe");
  docFrame.className = "lightbox-doc-frame hidden";
  docFrame.setAttribute("sandbox", "");
  docFrame.setAttribute("title", "Preview of this HTML file");
  doc.append(docNote, docBody, docEdit, docFrame, pdfPages);
  doc.addEventListener("click", (e) => e.stopPropagation());
  stage.appendChild(doc);

  // Find within the document. Deliberately a filter over the rendered text
  // rather than the browser's own Ctrl+F: this panel scrolls inside a
  // dialog, and the native find has no idea the rest of the page is inert.
  const find = document.createElement("input");
  find.type = "search";
  find.className = "lightbox-find hidden";
  find.placeholder = "Find in document";
  find.setAttribute("aria-label", "Find in document");
  const findCount = document.createElement("span");
  findCount.className = "muted lightbox-find-count hidden";
  const clearFind = () => {
    find.value = "";
    findCount.textContent = "";
    docBody.querySelectorAll("mark.lightbox-hit").forEach((m) => {
      m.replaceWith(document.createTextNode(m.textContent));
    });
    docBody.normalize();
  };
  find.addEventListener("input", () => {
    // Unwrap previous hits before re-scanning, or each keystroke would
    // search text already split across <mark> boundaries.
    docBody.querySelectorAll("mark.lightbox-hit").forEach((m) => {
      m.replaceWith(document.createTextNode(m.textContent));
    });
    docBody.normalize();
    const needle = find.value.trim();
    if (!needle) {
      findCount.textContent = "";
      findCount.classList.add("hidden");
      return;
    }
    // Walk text nodes and wrap matches. Text-node surgery rather than an
    // innerHTML replace, which would corrupt the rendered markup and is the
    // classic way this feature introduces an injection bug.
    const lower = needle.toLowerCase();
    const walker = document.createTreeWalker(docBody, NodeFilter.SHOW_TEXT);
    const targets = [];
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeValue.toLowerCase().includes(lower)) targets.push(node);
    }
    let hits = 0;
    for (const textNode of targets) {
      const parts = textNode.nodeValue.split(new RegExp(`(${escapeForFind(needle)})`, "gi"));
      if (parts.length < 2) continue;
      const frag = document.createDocumentFragment();
      for (const part of parts) {
        if (part.toLowerCase() === lower) {
          const mark = document.createElement("mark");
          mark.className = "lightbox-hit";
          mark.textContent = part;
          frag.appendChild(mark);
          hits += 1;
        } else if (part) {
          frag.appendChild(document.createTextNode(part));
        }
      }
      textNode.replaceWith(frag);
    }
    findCount.textContent = hits ? `${hits} match${hits === 1 ? "" : "es"}` : "No matches";
    findCount.classList.remove("hidden");
    docBody.querySelector("mark.lightbox-hit")?.scrollIntoView({ block: "center" });
  });
  actions.append(find, findCount);

  // Which suffixes this viewer renders as a *picture*. Everything else that
  // reaches the lightbox is offered to the document reader instead.
  const IMAGE_SUFFIXES = /\.(png|jpe?g|gif|webp|avif|bmp|ico|svg)$/i;

  // Reassigned on every `showDocument` call: see `readWithAiBtn` above,
  // which is the only caller. A closure rather than a stored url string so
  // the "Read with AI" button always re-derives from whichever item and
  // text-endpoint are current, the same way `show(i)` already recomputes
  // everything else per item rather than caching it.
  let lightboxLoadExtractedText = null;

  async function showDocument(item, name, attachmentId) {
    img.classList.add("hidden");
    broken.classList.add("hidden");
    doc.classList.remove("hidden");
    docBody.replaceChildren();
    pdfPages.replaceChildren();
    pdfPages.classList.add("hidden");
    docNote.classList.add("hidden");
    readWithAiBtn.classList.add("hidden");
    //: A new file, so any half-finished edit of the previous one goes with
    //: it. Cleared *before* the fetch rather than after: the two buttons are
    //: on screen the whole time it is in flight, and Save on a stale target
    //: would write one file's text over another's.
    lightboxEditTarget = null;
    docEdit.value = "";
    setLightboxEditing(false);
    editFileBtn.classList.add("hidden");
    lightboxPreviewSource = null;
    lightboxExtractedText = null;
    lightboxOcrTarget = null;
    //: A new file, so the previous one's page count, stepper and read-chips go
    //: with it: the PDF branch below re-establishes them when there are pages.
    resetDocPages();
    exportTextBtn.classList.add("hidden");
    clearDocPreview();
    previewHtmlBtn.classList.add("hidden");
    clearFind();
    find.classList.remove("hidden");

    // A native Tessellate document (the Documents list) or a real Attachment
    // row each has its own text/info endpoint; a `/media/` upload has a
    // third. All three converge on the same `AttachedFileTextOut` shape, so
    // everything past this point reads one variable rather than branching
    // three ways again and again.
    const textUrl = attachmentId
      ? `/files/${attachmentId}/text`
      : `/media/text/${encodeURIComponent(name)}`;
    const isPdf = /\.pdf$/i.test(item.filename || name || "");

    async function loadExtractedText() {
      // **The pages stay.** Reported directly: "when I select to read the
      // text from the document in a pdf, the pdf view disappears entirely. I
      // want the pdf view to be on one side, and the live extracted document
      // text and visuals on the right." Reading a scan *against* its pages is
      // the entire point: the text is a machine's reading of an image, and
      // hiding the image removes the only way to check it. So for a file
      // that has rendered pages, this becomes a split: pages left, text
      // right, both scrolling on their own. Anything without pages (a .docx,
      // a .txt) still gets the full width, because there is nothing to put
      // beside it.
      const hasPages = pdfPages.childElementCount > 0;
      doc.classList.toggle("lightbox-doc-split", hasPages);
      pdfPages.classList.toggle("hidden", !hasPages);
      docBody.classList.remove("hidden");
      find.classList.remove("hidden");
      showZoomControls(hasPages);
      if (!hasPages) setZoom(1);
      setLabel(docBody, "ph:spin Reading…");
      let payload = null;
      // See the doc-viewer comment block above `doc`'s own creation: a
      // native document already has its text, set by the Documents list's
      // "Preview" action: nothing to fetch.
      if (item.kind && item.text != null) {
        payload = { kind: item.kind, text: item.text, source: item.source || "file" };
      } else {
        try {
          payload = await apiJson(textUrl);
        } catch {
          payload = null;
        }
      }
      if (!payload) {
        docBody.textContent = "";
        docNote.textContent =
          "This file can't be previewed here. Use Save to open it in another app.";
        docNote.classList.remove("hidden");
        find.classList.add("hidden");
        return;
      }
      docBody.replaceChildren();
      const body = payload.text || "";
      //: **Decided before the empty-body return below, not after it.** A
      //: .docx on an install without markitdown extracts to nothing, so that
      //: return fires: and the read-only reason, which is exactly what such
      //: a file needs to say, used to be computed past it and never shown.
      //: Measured: the note read only "Importing documents needs the optional
      //: markitdown package", with no word about editing at all.
      //:
      //: **Preview is offered only for HTML**, and keyed off the *filename*
      //: rather than the extracted kind: docview reports `.html` as "code",
      //: which is right for how the source renders and says nothing about
      //: whether the file is a page. A .py is code too and has nothing to
      //: preview.
      if (body.trim()) {
        lightboxExtractedText = {
          name: item.filename || name || "document",
          kind: payload.kind,
          text: body,
        };
        exportTextBtn.classList.remove("hidden");
      }
      if (attachmentId && /\.html?$/i.test(item.filename || name || "") && body.trim()) {
        lightboxPreviewSource = `/files/${attachmentId}/html-preview`;
        previewHtmlBtn.classList.remove("hidden");
      }
      const editNotes = [];
      if (item.kind && item.text != null) {
        editFileBtn.classList.add("hidden");
      } else if (payload.editable) {
        lightboxEditTarget = { url: textUrl, text: body };
        editFileBtn.classList.remove("hidden");
      } else {
        editFileBtn.classList.add("hidden");
        if (payload.edit_message) editNotes.push(`Read-only: ${payload.edit_message}`);
      }
      if (!body.trim()) {
        docNote.textContent = [
          payload.message || "There's no readable text in this file.",
          ...editNotes,
        ].join(" · ");
        //: **The way to fix it, beside the reason** (the owner, 2026-10-10: "it
        //: failed to let me view the pdf doc I had as the package wasn't
        //: installed, it should have given me a link to nav to install or an
        //: install button directly"): one Install, opening Settings at that
        //: package's row, as the OCR engine line does (DESIGN.md).
        if (payload.extra) {
          const install = smallButton("ph:download-simple Install", "Open Settings, Packages at this package", () => {
            close();
            revealFeature("extra-row", payload.extra);
          }, false);
          docNote.append(" ", install);
        }
        docNote.classList.remove("hidden");
        return;
      }
      if (payload.kind === "markdown") {
        // The same renderer documents and chat use, so a previewed .md
        // looks like the same app rather than a second idea of markdown.
        renderMarkdown(docBody, body);
      } else {
        // Code and plain text keep their own whitespace, which is most of
        // what makes them readable.
        const pre = document.createElement("pre");
        pre.className = "lightbox-doc-pre";
        const code = document.createElement("code");
        if (payload.kind === "code") {
          //: §R7.1 item 3. `highlightCodeInto` (editor.js) picks the language
          //: off the filename and builds spans with `textContent`, so a file
          //: cannot inject markup by being written to look like markup.
          highlightCodeInto(code, body, item.filename || name || "");
        } else {
          code.textContent = body;
        }
        pre.appendChild(code);
        docBody.appendChild(pre);
      }
      // `source` is shown, not just logged: text a vision model
      // transcribed off a scanned page is a *reading* of the file, and
      // presenting it identically to text read out of a .txt would state a
      // guess as fact.
      const notes = [];
      if (payload.source === "vision-ocr") notes.push("Text read off the page by a vision model");
      else if (payload.source === "converted") notes.push("Converted for preview");
      if (payload.truncated) notes.push("Long file: showing the beginning only");
      if (payload.message) notes.push(payload.message);
      //: **The reason a file cannot be edited, shown where it is read.** §R7.1
      //: item 2 asked for the honest reason in the UI rather than a control
      //: that quietly does nothing. Computed above, beside the button it
      //: belongs to; pushed here so it reads as one line with the rest.
      notes.push(...editNotes);
      docNote.textContent = notes.join(" · ");
      docNote.classList.toggle("hidden", !notes.length);
    }
    lightboxLoadExtractedText = loadExtractedText;

    // A native document is markdown from the database, there is no PDF
    // underneath it to rasterise, so it always takes the text path above.
    if (isPdf && !item.kind) {
      const infoUrl = attachmentId ? `/files/${attachmentId}/pdf-info` : `/media/pdf-info/${encodeURIComponent(name)}`;
      const pageUrl = (i) =>
        attachmentId ? `/files/${attachmentId}/pdf-page/${i}` : `/media/pdf-page/${encodeURIComponent(name)}/${i}`;
      let info = null;
      try {
        info = await apiJson(infoUrl);
      } catch {
        info = null;
      }
      if (info && info.available && info.pages > 0) {
        docBody.classList.add("hidden");
        find.classList.add("hidden"); // nothing here is text to search yet
        //: The identity the OCR workspace needs, built here because this is
        //: the one place that knows whether the open file is an attachment or
        //: a media upload. `original_name` rather than the stored name: the
        //: workspace's own `ocrIsPdf` tests the extension of exactly that.
        //: `url` matters as much as `id` for an upload: the workspace renders a
        //: page through `/media/pdf-page/{stored name}/{n}`, not by id, so a
        //: target without it asked for `/media/pdf-page//0` and got a 404, the
        //: workspace opened on an empty stage. Measured against the running app
        //: while wiring the "open at this page" route in; the attachment side
        //: has an id-addressed page endpoint and never hit it.
        lightboxOcrTarget = attachmentId
          ? { id: attachmentId, _isAttachment: true, original_name: item.filename || name }
          : item.id
          ? {
              id: item.id,
              _isAttachment: false,
              original_name: item.filename || name,
              url: `/media/${name}`,
            }
          : null;
        readWithAiBtn.classList.remove("hidden");
        pdfPages.classList.remove("hidden");
        // Zoom, same as the image view, reported live once pages actually
        // rendered: "or zoom. a lot of controls are missing." `setZoom(1)`
        // resets any leftover magnification from a previously viewed item;
        // `zoomTarget()`/`applyZoom` (above) already know to scale
        // `pdfPages` rather than `img` while this view is the one showing.
        showZoomControls(true);
        setZoom(1);
        for (let i = 0; i < info.pages; i++) {
          const pageImg = document.createElement("img");
          pageImg.className = "lightbox-pdf-page";
          pageImg.loading = "lazy";
          pageImg.alt = `Page ${i + 1} of ${info.pages}`;
          pageImg.src = mediaSrc(pageUrl(i));
          pdfPages.appendChild(pageImg);
        }
        //: **The document block** (Phase 7.1). The page count is known right
        //: here and nowhere else, so this is where the stepper, the chips and
        //: the facts line are told about it. The chips render immediately as
        //: "not read yet" and the stored readings fill them in when they
        //: arrive: a panel that waits for a request before showing the page
        //: count would leave the viewer blank for the one fact it already has.
        docPageCount = info.pages;
        docPage = 0;
        showPageControls(info.pages > 1);
        renderDocPages();
        //: `renderInfo`, not the inline copy in `show()`'s image path: a
        //: document reaches the early return below, so nothing else would ever
        //: draw the facts line for it. Reported as part of the same item, 
        //: "no sections or info are below it really compared to the images."
        renderInfo(item, true);
        loadDocPageReads(attachmentId, name, item).catch(() => {});
        return;
      }
      // pdfpages isn't installed, or this particular file can't be opened: 
      // `info.message` already says which. Fall through to the AI-text path
      // below, which gives the same honest message (docview.py's own
      // "couldn't be opened" vs. "probably a scan" split) rather than a
      // second, differently-worded dead end.
    }
    await loadExtractedText();
  }

  async function show(i) {
    index = (i + items.length) % items.length;
    const item = items[index];
    // **`Promise.resolve()`, not a bare `.catch()` on the call.** Found live,
    // not by reading: this crashed the entire lightbox, not just the new
    // document detection: for the Library's own gallery, whose `getUrl` is
    // `() => mediaSrc(i.url)`, a plain synchronous string return, not a
    // Promise. `.catch` does not exist on a string, so this threw
    // synchronously and no code past it in `show()` ever ran, including the
    // metadata panel that predates this change entirely. `await` on a
    // non-Promise already resolves fine (`show()`'s other two `getUrl()`
    // call sites never hit this); wrapping in `Promise.resolve()` first is
    // what makes `.catch()` safe to chain regardless of which shape a
    // caller returns.
    const rawUrl = await Promise.resolve(item.getUrl()).catch(() => "");
    const name = (/\/media\/([^/?#]+)/.exec(rawUrl || "") || [])[1] || "";
    // A note's own attached file (the `Attachment` model, `/files/{id}`), 
    // distinct from a `/media/{name}` upload, and until now the only file
    // shape the lightbox's document viewer could not read at all: it went
    // straight to a download instead. Same token-gated url shape `mediaSrc`
    // already handles; `showDocument` below is what learned to use it.
    const looksLikeImage =
      IMAGE_SUFFIXES.test(item.filename || "") || IMAGE_SUFFIXES.test(name);
    // A note's own attached file (the `Attachment` model, `/files/{id}`), 
    // distinct from a `/media/{name}` upload, and until now the only file
    // shape the lightbox's document viewer could not read at all: it went
    // straight to a download instead. Same token-gated url shape `mediaSrc`
    // already handles; `showDocument` below is what learned to use it.
    //
    // Gated on `!looksLikeImage`, matching the `name` case just below it, 
    // the comment here used to claim this was "only ever set for a
    // non-image /files/{id}", true only because nothing had ever opened an
    // *image* attachment through this lightbox yet. The Library gallery's
    // own Attachment rows (`renderLibraryImagesGallery`, library.js) changed
    // that: a photo attached to a note now reaches this same code path, and
    // without this guard it fell into the document viewer below, no PDF
    // pages, no image to show, `isPdf` false, straight to `loadExtractedText`
    // asking `/files/{id}/text` for a picture, "no readable text in this
    // file" for what should have been a plain zoomable image.
    const attachmentId = name || looksLikeImage
      ? ""
      : (/\/files\/(\d+)(?:[/?#]|$)/.exec(rawUrl || "") || [])[1] || "";
    // A native document (item.kind already set: see showDocument) has no
    // `/media/...` url to sniff at all; a caller that already declares
    // itself a document skips the filename guess entirely.
    if (item.kind || attachmentId || (name && !looksLikeImage)) {
      overlay.setAttribute("aria-label", item.filename || "Document preview");
      syncChrome(item);
      actions.classList.remove("hidden");
      rotation = 0;
      setZoom(1);
      showZoomControls(false);
      openDocBtn.classList.toggle("hidden", !item.documentId);
      syncMoreMenu(item);
      await showDocument(item, name, attachmentId);
      syncDock();
      hydrate(index, item, true);
      return;
    }
    doc.classList.add("hidden");
    //: The page column too: left showing inside the hidden document, it was
    //: still `zoomTarget()`, so a picture paged to from a PDF zoomed the PDF.
    pdfPages.classList.add("hidden");
    rotation = 0;
    syncChrome(item);
    //: A picture is never a document, so paging from a previewed document to
    //: an image must take this away with the rest of the text controls.
    openDocBtn.classList.add("hidden");
    //: A picture has no text to edit, and leaving Edit/Save on the bar after
    //: paging from a .md to a .png would offer to write the note's markdown
    //: over an image. Cleared with the target, not just hidden.
    lightboxEditTarget = null;
    setLightboxEditing(false);
    editFileBtn.classList.add("hidden");
    lightboxPreviewSource = null;
    lightboxExtractedText = null;
    lightboxOcrTarget = null;
    //: A picture has no pages. Paging from a PDF to an image must take the
    //: stepper and the page chips with it, or the panel keeps offering "page 4
    //: of 9" for a photograph.
    resetDocPages();
    exportTextBtn.classList.add("hidden");
    clearDocPreview();
    previewHtmlBtn.classList.add("hidden");
    find.classList.add("hidden");
    findCount.classList.add("hidden");
    showZoomControls(true);
    img.alt = item.filename || "";
    img.src = rawUrl;
    // A failed decode used to be swallowed here, leaving a blank box with no
    // explanation: reported live as "the second page doesn't load" (an
    // image whose underlying file was gone, paged to from a gallery that
    // itself hides broken tiles, so the lightbox was the only place the
    // failure was ever visible, and it said nothing). Now it says so.
    const ok = await img.decode().then(
      () => true,
      () => false
    );
    img.classList.toggle("hidden", !ok);
    broken.classList.toggle("hidden", ok);
    if (!ok) broken.textContent = `Couldn't load "${item.filename || "this image"}", the file may have been deleted.`;
    overlay.setAttribute("aria-label", item.filename || "Image preview");
    syncTitle(item);
    const caption = (item.caption || "").trim();
    const text = (item.text || "").trim();
    infoCaption.textContent = caption;
    infoCaption.classList.toggle("hidden", !caption);
    infoCaptionByline.textContent = caption ? item.captionByline || "" : "";
    infoCaptionByline.classList.toggle("hidden", !caption || !item.captionByline);
    infoText.textContent = text;
    infoText.classList.toggle("hidden", !text);
    infoByline.textContent = item.byline || "";
    infoByline.classList.toggle("hidden", !item.byline);
    renderAltReading(item.altText, item.altByline);
    syncReadingDeletes(item, { text, alt: (item.altText || "").trim() });
    info.classList.toggle("hidden", !caption && !text && !item.filename);
    // The picture's own facts, which the app knew and never showed. Asked
    // for: "maybe it can have the image information and other info about it
    // below the image with the caption and ocr text??" Dimensions come from
    // the decoded image rather than from the server, it is the one fact the
    // browser already has and the API does not carry.
    const facts = [];
    if (ok && img.naturalWidth) facts.push(`${img.naturalWidth} × ${img.naturalHeight}`);
    if (item.addedAt) {
      const when = new Date(item.addedAt);
      if (!Number.isNaN(when.valueOf())) facts.push(`Added ${when.toLocaleDateString()}`);
    }
    if (item.filename) facts.push(item.filename);
    infoFacts.textContent = facts.join("  ·  ");
    infoFacts.classList.toggle("hidden", !facts.length);
    // Paging to another picture starts it at fit, the same way opening one
    // does: carrying a 400% zoom onto the next image lands you somewhere
    // arbitrary in a picture you have not seen yet.
    setZoom(1);
    copyBtn.classList.toggle("hidden", !text);
    // Nothing to act on when the file itself failed to load.
    actions.classList.toggle("hidden", !ok);
    syncMoreMenu(item);
    syncInfoWanted();
    syncDock();

    // **Fill in whatever the caller did not know.** Reported directly: the
    // caption, OCR text and facts appeared in the Image Gallery and nowhere
    // else. The lightbox was never the problem, this metadata arrived as
    // *arguments*, and of nine callers only the gallery holds a full media
    // row to pass. Everywhere else (a note attachment, a chat image, a graph
    // or dashboard thumbnail, a whiteboard object) has a url and a name, so
    // the panel below the picture stayed empty on the same picture that
    // showed a full description one tab over.
    //
    // Asking the server closes that gap in one place instead of nine, and
    // covers callers added later without them having to know to pass
    // anything. Only ever *fills*: a caller that did pass a caption keeps
    // the one it passed, so the gallery's own (possibly just-edited,
    // not-yet-saved) values still win.
    hydrate(index, item, ok);
  }

  // Looked up once per filename per lightbox, then remembered: paging back
  // and forth across a gallery would otherwise refetch the same rows.
  const metaCache = new Map();
  async function hydrate(forIndex, item, ok) {
    if (item.caption && item.text && item.addedAt) return;
    let url;
    try {
      url = await item.getUrl();
    } catch {
      return;
    }
    // `/media/<stored name>`, possibly with a query string (an address
    // saved before 2026-09-24 can still carry one), which is not part of the
    // name.
    const match = /\/media\/([^/?#]+)/.exec(url || "");
    if (!match) return;
    const name = match[1];
    if (!metaCache.has(name)) {
      metaCache.set(
        name,
        apiJson(`/media/meta/${encodeURIComponent(name)}`).catch(() => null)
      );
    }
    const row = await metaCache.get(name);
    // Not an error worth surfacing: plenty of images in this app are not
    // `MediaUpload` rows at all (a sketch rendered straight to a data url,
    // a file whose row was deleted out from under a note that still links
    // it). No metadata simply means no panel, exactly as before.
    if (!row) return;
    // The picture may have been paged away from while this was in flight.
    if (forIndex !== index) return;

    const readings = lightboxReadingsFor(row);
    if (!item.caption && row.caption) item.caption = row.caption;
    if (row.id && !item.metaId) item.metaId = row.id;
    if (!item.text) {
      item.text = readings.text;
      item.textSource = readings.textSource;
    }
    if (!item.addedAt && row.created_at) item.addedAt = row.created_at;
    if (!item.byline) item.byline = readings.byline;
    //: The alternate is filled whenever the row has one, rather than only when
    //: the item arrived without it: a caller that passed a reading but knew
    //: nothing of the second one (every caller with a bare url) would otherwise
    //: keep the panel one reading short for the whole visit.
    if (!item.altText) {
      item.altText = readings.altText;
      item.altByline = readings.altByline;
      item.altSource = readings.altSource;
    }
    if (!item.captionByline) item.captionByline = captionBylineFor(row);
    // The gallery passes `original_name`; a bare url caller passes the
    // stored name or nothing, and the human-readable one is better.
    if (row.original_name && (!item.filename || item.filename === name)) {
      item.filename = row.original_name;
    }
    renderInfo(item, ok);
  }

  // The half of `show()` that draws the panel, split out so `hydrate` can
  // redraw it once the answer arrives without re-running the image load.
  //: Which item the info panel was last drawn for, so a page change can redraw
  //: it without `show()` having to hand the item down through the stepper.
  let lightboxInfoItem = null;

  function renderInfo(item, ok) {
    lightboxInfoItem = item;
    //: **For a document, the panel is about the page on screen** (Phase 7.3).
    //: The file-level values are one caption for a whole PDF, which describes
    //: none of its pages, and the *joined* reading of every page, which is
    //: not what you are looking at when page 4 is up. `docPageRows` has both,
    //: per page, from the `PageRead` store; a page with neither falls back to
    //: the file's own values so nothing that used to show now disappears.
    const row = docPageCount ? docPageRows.get(docPage) : null;
    const perPage = Boolean(row && (row.text || row.caption));
    const caption = perPage ? row.caption : (item.caption || "").trim();
    const text = perPage ? row.text : (item.text || "").trim();
    const captionByline = perPage
      ? row.caption_model
        ? `Figures on page ${docPage + 1}, described by ${shortModelName(row.caption_model)}`
        : ""
      : item.captionByline || "";
    const byline = perPage
      ? row.model
        ? `Page ${docPage + 1}, read by ${shortModelName(row.model)}`
        : row.text
          ? `Page ${docPage + 1}`
          : ""
      : item.byline || "";
    //: What Copy hands over has to be what is on screen: copying every page's
    //: reading while the panel shows one page's is the app disagreeing with
    //: itself about what "this text" means.
    lightboxShownText = text;
    infoCaption.textContent = caption;
    infoCaption.classList.toggle("hidden", !caption);
    infoCaptionByline.textContent = caption ? captionByline : "";
    infoCaptionByline.classList.toggle("hidden", !caption || !captionByline);
    infoText.textContent = text;
    infoText.classList.toggle("hidden", !text);
    infoByline.textContent = byline;
    infoByline.classList.toggle("hidden", !byline);
    //: Not on a page of a document: `docPageRows` holds one reading per page
    //: (`PageRead`), so there is no second reader to footnote there, and the
    //: file-level alternate would be a claim about the whole PDF sitting under
    //: page 4's own text.
    renderAltReading(perPage ? "" : item.altText, item.altByline);
    syncReadingDeletes(item, { text, alt: perPage ? "" : (item.altText || "").trim(), perPage });
    info.classList.toggle("hidden", !caption && !text && !item.filename);
    syncTitle(item);
    syncInfoWanted();
    const facts = [];
    //: A document's dimensions are its *pages*, and the picture's pixel size
    //: is meaningless for one, `docPageCount` is 0 for anything that is not a
    //: rendered PDF, so an image is unaffected.
    if (docPageCount) {
      facts.push(`${docPageCount} page${docPageCount === 1 ? "" : "s"}`);
      facts.push(
        docPagesRead.size
          ? `${docPagesRead.size} read`
          : "none read yet"
      );
    } else if (ok && img.naturalWidth) {
      facts.push(`${img.naturalWidth} × ${img.naturalHeight}`);
    }
    if (item.addedAt) {
      const when = new Date(item.addedAt);
      if (!Number.isNaN(when.valueOf())) facts.push(`Added ${when.toLocaleDateString()}`);
    }
    if (item.filename) facts.push(item.filename);
    infoFacts.textContent = facts.join("  ·  ");
    infoFacts.classList.toggle("hidden", !facts.length);
    copyBtn.classList.toggle("hidden", !text);
    copyBtn.title = perPage
      ? `Copy the text read from page ${docPage + 1}`
      : "Copy the text read from this image";
  }

  //: Per file: the title and count, the filmstrip's current tile, what the
  //: top bar can offer for this kind of file.
  function syncChrome(item) {
    syncTitle(item);
    syncFilmstrip();
    openTabBtn.classList.toggle("hidden", Boolean(item.kind));
    for (const b of [dockPrevBtn, dockNextBtn]) b.classList.toggle("hidden", items.length < 2);
  }
  //: The dock goes when nothing in it applies (a text file has no zoom and
  //: no pages, and the phone's arrows are only for more than one file).
  function syncDock() {
    const phone = window.matchMedia("(max-width: 599.98px)").matches;
    const live = [...dock.querySelectorAll("button")].some(
      (b) => !b.classList.contains("hidden") && (phone || !b.classList.contains("lightbox-dock-nav"))
    );
    dock.classList.toggle("hidden", !live);
  }

  //: **Quiet chrome** (the brief's "auto-hide controls on idle with pointer
  //: reveal"). Only a mouse resting on the picture fades the bars: a key, a
  //: visible focus ring, an open menu or popover, or reduced motion keeps
  //: them, so nobody working from the keyboard ever loses a control.
  const IDLE_MS = 2600;
  let idleTimer = 0;
  let keysSeen = false;
  const canRest = () =>
    !keysSeen &&
    !reducedMotion() &&
    overlay.isConnected &&
    !overlay.querySelector(":focus-visible") &&
    !document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden)");
  const wake = (e) => {
    overlay.classList.remove("lightbox-idle");
    clearTimeout(idleTimer);
    if (e && e.pointerType === "mouse" && stageWrap.contains(e.target)) {
      idleTimer = setTimeout(() => {
        if (canRest()) overlay.classList.add("lightbox-idle");
      }, IDLE_MS);
    }
  };
  overlay.addEventListener("pointermove", wake);
  overlay.addEventListener("pointerdown", wake);
  overlay.addEventListener("wheel", wake, { passive: true });

  const close = () => {
    clearTimeout(idleTimer);
    filmSeen?.disconnect();
    overlay.remove();
    setFullscreenSurface("lightbox", false);
    document.removeEventListener("keydown", onKey, true);
  };
  //: Typing keeps its keys: the find box and the file editor are inside this
  //: dialog, and an arrow there moves the caret, not the file.
  const typing = (el) => el instanceof Element && el.matches("input, textarea, select, [contenteditable=''], [contenteditable='true']");
  const onKey = (e) => {
    keysSeen = true;
    wake();
    //: A menu, a popover or a confirm over the viewer has the keys first.
    const above = document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden), .confirm-overlay:not(.hidden)");
    if (e.key === "Escape") {
      if (!above) close();
      return;
    }
    if (above || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    const picture = !img.classList.contains("hidden") && doc.classList.contains("hidden");
    const zoomable = picture || !pdfPages.classList.contains("hidden");
    const key = e.key;
    if (key === "ArrowLeft" && items.length > 1) show(index - 1);
    else if (key === "ArrowRight" && items.length > 1) show(index + 1);
    else if (key === "Home" && items.length > 1 && picture) show(0);
    else if (key === "End" && items.length > 1 && picture) show(items.length - 1);
    else if ((key === "+" || key === "=") && zoomable) zoomBy(1.5);
    else if ((key === "-" || key === "_") && zoomable) zoomBy(1 / 1.5);
    else if (key === "0" && zoomable) fitView();
    else if (key === "1" && picture) actualSize();
    else if ((key === "r" || key === "R") && picture) turn();
    else if ((key === "i" || key === "I") && !infoBtn.classList.contains("hidden")) infoBtn.click();
    else return;
    e.preventDefault();
  };
  // Only empty space closes on click, the picture, the metadata and the
  // nav/close buttons all need to stay clickable without dismissing the
  // dialog they sit inside. The three layout boxes named here have no content
  // of their own: the column is full-window-width and only as tall as the
  // picture, so without them the entire band left and right of the image was
  // dead to a dismissing click. See `wireBackdropClose`.
  wireBackdropClose(overlay, close, ".lightbox-column, .lightbox-stage-wrap, .lightbox-stage");
  closeBtn.addEventListener("click", close);
  prevBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    show(index - 1);
  });
  nextBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    show(index + 1);
  });
  //: Capture: a menu or the help popover closes itself on its own Escape
  //: listener, and by the bubble this one would see it already gone and
  //: close the viewer under it too.
  document.addEventListener("keydown", onKey, true);

  stage.append(img, broken);
  // **The arrows must not live inside the stage.** The stage scrolls now
  // (zoom needs it to, so a magnified picture can be panned to its edges),
  // and an absolutely-positioned child of a scrolling box scrolls with its
  // content: so the arrows drifted off-centre and away from the edges the
  // moment anything overflowed. Reported live: "completely off, different
  // distances from the edge of the screen, at different heights, and not
  // even aligned."
  //
  // A non-scrolling wrapper holds both: the stage scrolls inside it, the
  // arrows are positioned against it, and because the wrapper is exactly
  // the stage's box, `top: 50%` is still the middle of the picture, which
  // is the property the note on `.lightbox-nav` says two earlier attempts
  // lost.
  const stageWrap = document.createElement("div");
  stageWrap.className = "lightbox-stage-wrap";
  stageWrap.appendChild(stage);
  //: `lightbox-paged` narrows the stage by the arrows' room, so the picture
  //: never goes under one (02-chat-graph.css).
  if (items.length > 1) {
    stageWrap.append(prevBtn, nextBtn);
    stageWrap.classList.add("lightbox-paged");
  }
  const column = document.createElement("div");
  column.className = "lightbox-column";
  column.append(stageWrap, actions, info);
  bottom.append(film, dock);
  overlay.classList.add("lightbox-framed");
  overlay.append(topbar, column, bottom);
  document.body.appendChild(overlay);
  setFullscreenSurface("lightbox", true);
  closeBtn.focus();
  //: `.then`, not `await`: `openLightbox` is not async and its nine callers
  //: do not expect it to be. The dialog is already on screen and interactive
  //: by the time this resolves; all that is left is where to point the reader.
  Promise.resolve(show(startIndex)).then(() => {
    if (!opts.focusReading) return;
    //: Start on the first page that actually has a reading. Page 1 of a scan
    //: is often a cover, and "open the reading" landing on a page with none is
    //: the same disappointment as not opening it at all.
    if (docPageCount && docPagesRead.size) {
      setDocPage(Math.min(...docPagesRead));
    }
    //: `block: "end"` because the panel sits *under* the file: bringing its
    //: bottom into view is what puts the reading on screen, where "nearest"
    //: would decide it is already close enough and do nothing.
    info.scrollIntoView({ block: "end" });
    //: Focus follows the eye. `-1` so it is a destination rather than another
    //: stop on the way through the dialog's own controls.
    infoText.tabIndex = -1;
    infoText.focus();
  });
}

// ---- from editor.js (search-boot-1005): highlightCodeInto ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

//: Fills `target` with the highlighted source. Text nodes and `<span>`s
//: built with `textContent`, never `innerHTML`, a file's own text is exactly
//: the untrusted input a markup-assembling highlighter turns into an
//: injection, and this app's CSP would not save a same-origin one.
function highlightCodeInto(target, text, filename) {
  const scanner = codeScanner(codeFamilyFor(filename));
  scanner.lastIndex = 0;
  const source = String(text ?? "");
  let at = 0;
  let match;
  while ((match = scanner.exec(source)) !== null) {
    //: A zero-length match would loop forever. None of the patterns above can
    //: produce one, and this costs nothing to be certain of.
    if (match.index === scanner.lastIndex) {
      scanner.lastIndex++;
      continue;
    }
    if (match.index > at) target.appendChild(document.createTextNode(source.slice(at, match.index)));
    const kind = Object.keys(match.groups).find((name) => match.groups[name] !== undefined);
    const span = document.createElement("span");
    span.className = `tok-${kind}`;
    span.textContent = match[0];
    target.appendChild(span);
    at = match.index + match[0].length;
  }
  if (at < source.length) target.appendChild(document.createTextNode(source.slice(at)));
}

// ---- from editor.js (search-boot-1005): codeScanner ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

function codeScanner(family) {
  if (codeScanners.has(family)) return codeScanners.get(family);
  const lineComment =
    family === "hash" ? "#[^\\n]*" : family === "sql" ? "--[^\\n]*" : "\\/\\/[^\\n]*";
  const parts = [];
  if (family === "markup") parts.push("(?<comment><!--[\\s\\S]*?-->)");
  else parts.push(`(?<comment>\\/\\*[\\s\\S]*?\\*\\/|${lineComment})`);
  parts.push('(?<string>"(?:[^"\\\\\\n]|\\\\.)*"|\'(?:[^\'\\\\\\n]|\\\\.)*\'|`(?:[^`\\\\]|\\\\.)*`)');
  parts.push("(?<number>\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)");
  const words = (CODE_KEYWORDS[family] || CODE_KEYWORDS.generic).trim().split(/\s+/);
  if (words.length && words[0]) parts.push(`(?<keyword>\\b(?:${words.join("|")})\\b)`);
  const scanner = new RegExp(parts.join("|"), "g");
  codeScanners.set(family, scanner);
  return scanner;
}

//: Which family a filename is in. Extension only: content sniffing guesses
//: wrong on short files and there is nothing to gain: a file this app can
//: view arrived with a suffix it recognised (`docview.CODE_SUFFIXES`).
function codeFamilyFor(filename) {
  const suffix = /\.([a-z0-9]+)$/i.exec(String(filename || ""));
  return CODE_LANGUAGES[(suffix?.[1] || "").toLowerCase()] || "generic";
}
