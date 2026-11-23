// shared-intake.js: a share from the phone's share sheet lands in Capture.
// Moved out of app.js on 2026-10-11 to give the boot scripts their bytes back
// (tests/test_static_compression.py): only a page opened from the share sheet
// carries `share_*`, and startApp fetches this file just then.

// --- a share from the phone's share sheet lands in Capture -------------------
// UI_MODERNISATION_PLAN Phase 11 item 5, "upload from the share sheet". The
// installed app is a Web Share Target (manifest.webmanifest): a page, a
// link or a selection shared to Tessellate opens the app at `/` with
// `share_title`, `share_text` and `share_url` in the query, the GET form,
// which needs no service worker and works on a locked notebook because the
// query survives the lock screen (this runs once the entries have loaded,
// which is after the unlock). The pieces become one capture: the title as
// a heading, the text, the link on its own line, so the link stays a link.
// The query is then cleared from the address bar, or a reload would share
// it again. Files (an image shared from the camera roll) come by the POST
// form: the service worker keeps them in the `tessellate-share-inbox` cache
// and sends `share_files` with their count (sw.js `takeShare`); they are
// staged in the composer as a paste would be (`handleFileUpload`), then the
// cache is emptied.
(() => {
  const SHARE_PARAMS = ["share_title", "share_text", "share_url", "share_files"];
  const SHARE_CACHE = "tessellate-share-inbox";

  function sharedCaptureText(params) {
    const title = (params.get("share_title") || "").trim();
    const text = (params.get("share_text") || "").trim();
    const url = (params.get("share_url") || "").trim();
    const lines = [];
    if (title && title !== text) lines.push(`# ${title}`);
    if (text) lines.push(text);
    if (url && !text.includes(url)) lines.push(url);
    return lines.join("\n\n");
  }

  //: The files the service worker kept, as File objects, oldest first; the cache is emptied either way.
  async function sharedFiles(count) {
    if (!count || !window.caches) return [];
    try {
      const cache = await caches.open(SHARE_CACHE);
      const files = [];
      for (let index = 0; index < count; index += 1) {
        const hit = await cache.match(`/share-inbox/${index}`);
        if (!hit) continue;
        //: Each name on its own: one that will not decode threw to the catch below and lost every file.
        let name = `shared-${index}`;
        try {
          name = decodeURIComponent(hit.headers.get("X-Share-Name") || name);
        } catch {}
        files.push(new File([await hit.blob()], name, { type: hit.headers.get("Content-Type") || "" }));
      }
      return files;
    } catch {
      return [];
    } finally {
      caches.delete(SHARE_CACHE).catch(() => {});
    }
  }

  async function takeSharedIntake() {
    const params = new URLSearchParams(window.location.search);
    if (!SHARE_PARAMS.some((key) => params.has(key))) return;
    const content = sharedCaptureText(params);
    const fileCount = Math.min(Number.parseInt(params.get("share_files") || "0", 10) || 0, 10);
    for (const key of SHARE_PARAMS) params.delete(key);
    const rest = params.toString();
    history.replaceState(null, "", `${location.pathname}${rest ? `?${rest}` : ""}${location.hash}`);
    const files = await sharedFiles(fileCount);
    if (!content && !files.length) return;
    const box = $("entry-content");
    if (!box) return;
    switchTab("notes");
    showNotesSection("capture");
    if (content) {
      box.value = box.value ? `${box.value}\n\n${content}` : content;
      box.dispatchEvent(new Event("input", { bubbles: true }));
    }
    box.focus();
    if (files.length) {
      //: Staged like a paste into the composer: pictures inline at the end, other files under it, all saved with the note.
      if (box.value && !box.value.endsWith("\n")) box.value += "\n\n";
      box.setSelectionRange(box.value.length, box.value.length);
      await handleFileUpload(box, files);
    }
    //: app.js's door fetches the library bundle first; a bare mountNoteSurface is documents.js's, which may not be in yet.
    mountNoteSurfaceNow(box).then((surface) => surface?.focus()).catch(() => {});
    toast("Shared to your notebook. Save it when it reads right.");
  }

  Object.assign(window, { takeSharedIntake });
})();
