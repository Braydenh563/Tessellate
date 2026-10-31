// The web clipper's window (WORLD_CLASS_PLAN D9, row 24): clip.html.
//
// Fully local. The bookmarklet (Settings, Import & export, Web clipper) runs
// in the page being read, opens this window on the app's own address, and
// sends it the page: first its address, title and selected text in this
// page's fragment (enough on its own), then, when this page says it is ready,
// the page's HTML by `postMessage`. Nothing is fetched from the web.
//
// Two rules make it safe to open from any site:
// - the HTML is taken only from the window that opened this one
//   (`event.source !== window.opener` is dropped), and only once;
// - nothing is saved until the person presses Save, so a page that opens
//   this window on its own can at most fill a preview nobody keeps.
// The note is stored with its address (`source_url`), which marks it as text
// from outside for the agent's guard and the prompt fence.

(() => {
  const $ = (id) => document.getElementById(id);
  const MAX_HTML = 3_000_000;
  const clip = { url: "", title: "", selection: "", html: "" };
  let saved = false;

  //: What the app saved in this browser: the session token, and the space
  //: open there (`activeSpaceId`, spaces-find.js), so a capture lands where
  //: the person is working rather than in the default space.
  function stored(key) {
    try {
      return localStorage.getItem(key) || "";
    } catch {
      return "";
    }
  }
  const token = () => stored("token");

  function status(text, isError = false) {
    const line = $("clip-status");
    line.textContent = text;
    line.classList.toggle("error", isError);
  }

  function describe() {
    $("clip-preview").classList.remove("hidden");
    if (!$("clip-title").value) $("clip-title").value = clip.title || clip.url;
    $("clip-source").textContent = clip.url;
    const words = wordCount(clip.selection);
    $("clip-what").textContent = clip.selection
      ? `The ${nounCount(words, "word")} you selected.`
      : clip.html
        ? "The page's main text, without its menus and footer."
        : "The address and title only (this page did not send its text).";
    $("clip-save").disabled = !clip.url || saved;
    status(token() ? "Check the title, then save." : "Sign in to Tessellate in this browser first, then clip again.", !token());
    $("clip-open").classList.toggle("hidden", Boolean(token()));
  }

  function fromFragment() {
    const raw = location.hash.slice(1);
    if (!raw) return;
    try {
      const data = JSON.parse(decodeURIComponent(raw));
      clip.url = String(data.u || "").slice(0, 2000);
      clip.title = String(data.t || "").slice(0, 300);
      clip.selection = String(data.s || "");
    } catch {
      // A fragment this page did not write: nothing to show from it.
    }
  }

  window.addEventListener("message", (event) => {
    if (!window.opener || event.source !== window.opener) return;
    const data = event.data;
    if (!data || data.type !== "memorymap-clip" || clip.html) return;
    clip.url = String(data.url || clip.url).slice(0, 2000);
    clip.title = String(data.title || clip.title).slice(0, 300);
    clip.selection = String(data.selection || clip.selection).slice(0, 200_000);
    clip.html = String(data.html || "").slice(0, MAX_HTML);
    describe();
  });

  //: The window's one request: signed in, in the space open in the app.
  const call = (path, method, body) =>
    fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "X-Auth-Token": token(), "X-Workspace-ID": stored("spaceId") || "all" },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });

  async function save() {
    const button = $("clip-save");
    button.disabled = true;
    status("Saving…");
    try {
      const response = await call("/links/clip-page", "POST", {
        url: clip.url,
        title: $("clip-title").value.trim() || clip.title,
        html: clip.selection ? "" : clip.html,
        selection: clip.selection,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : "";
        throw new Error(response.status === 401 ? "Sign in to Tessellate in this browser first, then clip again." : detail || "Couldn't save this page.");
      }
      saved = true;
      status(body.existing ? "Already in your notes, so nothing new was saved." : "Saved as a note. It is being filed now.");
      $("clip-open").classList.remove("hidden");
      //: A clip that made a note is on the app window's Undo stack when one is
      //: open, and otherwise offers its own Undo here (standalone-undo.js).
      const made = body.entry;
      if (!body.existing && made?.id != null && !(await window.standaloneUndo.announce(made, "Clipped a page"))) {
        window.standaloneUndo.offer({ id: made.id, send: call, status, row: document.querySelector(".clip-actions") });
      }
      try {
        window.opener?.postMessage("memorymap-clip-ok", "*");
      } catch {
        // The page that opened this one may have gone; the note is saved.
      }
    } catch (error) {
      status(error.message || "Couldn't save this page.", true);
      button.disabled = false;
    }
  }

  $("clip-save").addEventListener("click", save);
  $("clip-close").addEventListener("click", () => window.close());
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") window.close();
  });

  fromFragment();
  if (clip.url) describe();
  else status("Open this from the Clip to Tessellate bookmark on the page you want to keep.");
  // Ask the opener for the page itself. The message carries nothing.
  try {
    window.opener?.postMessage("memorymap-clip-ready", "*");
  } catch {
    // No opener (opened by hand, or the site cut the link): the fragment is enough.
  }
})();
