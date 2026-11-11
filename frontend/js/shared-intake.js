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
// it again. Files (an image shared from the camera roll) need the POST form
// and a service worker and are not taken here.
(() => {
  const SHARE_PARAMS = ["share_title", "share_text", "share_url"];

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

  function takeSharedIntake() {
    const params = new URLSearchParams(window.location.search);
    if (!SHARE_PARAMS.some((key) => params.has(key))) return;
    const content = sharedCaptureText(params);
    for (const key of SHARE_PARAMS) params.delete(key);
    const rest = params.toString();
    history.replaceState(null, "", `${location.pathname}${rest ? `?${rest}` : ""}${location.hash}`);
    if (!content) return;
    const box = $("entry-content");
    if (!box) return;
    switchTab("notes");
    showNotesSection("capture");
    box.value = box.value ? `${box.value}\n\n${content}` : content;
    box.dispatchEvent(new Event("input", { bubbles: true }));
    box.focus();
    //: app.js's door fetches the library bundle first; a bare mountNoteSurface is documents.js's, which may not be in yet.
    mountNoteSurfaceNow(box).then((surface) => surface?.focus()).catch(() => {});
    toast("Shared to your notebook. Save it when it reads right.");
  }

  Object.assign(window, { takeSharedIntake });
})();
