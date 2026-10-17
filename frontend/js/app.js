// Tessellate frontend: plain JS, no framework (locked decision, plan §2).
// All DOM nodes are built with createElement/textContent, never innerHTML,
// so a note containing <script> is just text, not code.
//
// This is the first of the app's 23 classic scripts (2026-09-26, INBOX 426
// cc, docs/roadmap/agent-remaining/appjs-split.md): the log capture, `api`,
// the auth gate, the share-sheet intake, the confirm dialogs and the lazy
// loader. note-cards.js to spaces-find.js follow it in index.html, each a
// contiguous range of what was one 50,000-line file, in its old order, and
// all of them share one global scope, so a function in any of them is
// callable from any other once the page has loaded. At load it is
// different: a file may only call into files before it, which is what
// scratchpad/appjs-map.js --check and tests/test_frontend_load_order.py
// check. Tests read all of them as one text through tests/_app_js.py.

// --- browser log capture (Wave A) -----------------------------------------------
// Installed before anything else runs so no message is missed. Shown in
// Settings → Logs alongside the server's records.

const browserLogs = [];
const MAX_BROWSER_LOGS = 500;

function recordBrowserLog(level, parts) {
  const record = {
    time: new Date().toISOString(),
    level,
    message: parts
      .map((p) => {
        if (typeof p === "string") return p;
        try {
          return JSON.stringify(p);
        } catch {
          return String(p);
        }
      })
      .join(" "),
  };
  browserLogs.push(record);
  if (browserLogs.length > MAX_BROWSER_LOGS) browserLogs.shift();

  // Live-push into the Logs page if it is currently open.
  // `logRecords`, `logScreenOpen`, `sortLogRecords`, `renderActiveLogView`,
  // `scrollLogToBottom` and `bumpLogErrorBadge` all live in settings.js now
  // (§88.3 item 4; previously later in this same file), which loads after
  // this one: so any `console.*` call during app.js's own early boot,
  // before settings.js has run, needs the same typeof guard this line
  // needed even when everything was one file. Confirmed live: this is
  // exactly the path a `console.warn`/`console.error` fired from app.js's
  // own startup would take, and it already degrades to "skip the live
  // push" rather than throwing, same as before the split.
  if (typeof logRecords !== "undefined" && typeof logScreenOpen !== "undefined") {
    logRecords.push({ ...record, source: "browser", logger: "browser", key: `b-live-${Math.random()}` });
    //: The four are settings.js's, beside `logRecords`.
    sortLogRecords();
    if (logScreenOpen) {
      renderActiveLogView();
      // Scroll to bottom so the new error is visible without manual scroll.
      scrollLogToBottom();
    }
    // Bump the error badge in the Logs button so the user knows to check.
    bumpLogErrorBadge(record);
  }
}

for (const level of ["log", "info", "warn", "error"]) {
  const original = console[level].bind(console);
  console[level] = (...parts) => {
    recordBrowserLog(level.toUpperCase(), parts);
    original(...parts);
  };
}
//: "ResizeObserver loop completed with undelivered notifications" is the
//: browser saying it deferred a resize callback one frame, not an
//: exception (no `e.error`, nothing thrown): logged as ERROR it filled the
//: owner's console from the Library's Files view (release, 2026-09-27).
//: The observer behind it is in the carry-over list; this only stops the
//: notice being reported as a failure.
const BENIGN_BROWSER_NOTICE = /^ResizeObserver loop (completed with undelivered notifications|limit exceeded)/;
window.addEventListener("error", (e) =>
  BENIGN_BROWSER_NOTICE.test(e.message || "") || !e.filename ? undefined :
  // e.error.stack, when present, is what actually locates the bug, the
  // message/filename/lineno triple alone has sent more than one session
  // hunting for a null-dereference with no line number to start from.
  recordBrowserLog("ERROR", [
    `${e.message} (${e.filename}:${e.lineno}:${e.colno})`,
    e.error?.stack || "",
  ])
);
window.addEventListener("unhandledrejection", (e) =>
  recordBrowserLog("ERROR", [
    "Unhandled promise rejection:",
    e.reason?.stack || String(e.reason),
  ])
);

// Below this confidence an entry gets a "check this" flag (plan Phase 3).
const REVIEW_THRESHOLD = 50;

let allEntries = []; // latest GET /entries result, newest first
// Whether that has ever come back. An empty notebook and a notebook that
// has not loaded yet look identical from `allEntries.length` alone.
let entriesEverLoaded = false;
// Bumped by every loadEntries() call, checked by its own background page
// fetches before they touch allEntries, the same "stale response" guard
// loadOnboardingDiagnostics uses. loadEntries can page in the background for
// a large notebook (see ENTRIES_PAGE_SIZE below), and loadEntries can also
// be called again mid-page-load (saving a note, deleting a category), a
// slow page from the *first* call landing after a second call already
// replaced allEntries would silently splice stale/duplicate rows back in.
let _entriesLoadGeneration = 0;
let activeCategory = null; // sidebar filter; null = All
// A second, orthogonal sidebar filter (not a category): asked for
// directly, so drafts (Writing Room saves, "Save as draft note" captures)
// are findable as a group instead of only a per-note chip. Mutually
// exclusive with activeCategory: picking one clears the other, same as
// switching categories already does.
let draftsOnly = false;
// **Favourites, as a third sidebar filter over a flag that already existed.**
// Asked for: "there should be a favourites folder or side parallel category
// that isnt an actual category but could be treated as one if toggled?? for
// notes??"
//
// Built on `entry.pinned` rather than on a new "starred" column, and that is
// the whole design decision. `pinned` is already per-note, already persisted,
// already toggled from a note's own chip, and already searchable as
// `is:pinned`, a second boolean meaning almost the same thing would be two
// half-used flags and two places to star something, which is exactly the
// "everything is different from everything else" this round is undoing. What
// was missing was never the data; it was the *place*: a row in the sidebar you
// can click, alongside the categories, the way Drafts already is.
//
// So `pinned` keeps its sort meaning (float to the top) and gains a collection
// meaning (a group you can go to). The same note is in both readings.
let favouritesOnly = false;
let linkSource = null; // entry id waiting for its link partner
let editingId = null; // entry id currently in inline-edit mode
//: Set by the "No tags yet" chip: the next edit form for this id opens with
//: its tags field focused. Read and cleared by renderEditForm.
let focusTagsAfterRender = null;
//: The note whose edit form takes the caret once drawn (openNoteEditor).
let focusBodyAfterRender = null;
let inlineAction = null; // {id, kind: "context"|"continue"} open on a card
let busyEntryId = null; // entry the AI is currently working on (spinner shown)
let flashConfidenceId = null; // entry whose confidence badge just changed (flash once)
let noteSearch = ""; // Notes-tab text filter (Wave J)
// Why each note is in the filtered list, keyed by id: `{explain, scores}` from
// `GET /search` (the retrieval engine, Brief 11). The list itself is still
// filtered here in the browser, which is what keeps typing instant; this is
// the *explanation* the browser cannot produce, because two of the three
// signals (meaning, and distance over the links) only exist on the server.
// Cleared whenever the box is, so a stale reason can never outlive its query.
const noteSearchWhy = new Map();
//: UX-04: /search's typo correction for the Notes box.
let noteSearchCorrection = null;
let noteSearchCorrectionShown = false;
let noteSort = "newest"; // newest | oldest | az | most-used (Wave J)
// BACKLOG §77 item 1. "all" (the default) keeps the existing continuous
// scroll (§86's renderIncrementally) untouched; a numeric size switches
// renderEntries to a single flat page of that many notes instead. Persisted
// the same way graph-gravity/graph-spread are, a plain localStorage read at
// declaration time, not the async preferences endpoint, since this is a
// display choice with no reason to round-trip the server.
let notesPageSize = localStorage.getItem("notes-page-size") || "all";
let notesCurrentPage = 1;

const $ = (id) => document.getElementById(id);
const show = (...ids) => ids.forEach((id) => $(id).classList.remove("hidden"));
const hide = (...ids) => ids.forEach((id) => $(id).classList.add("hidden"));

// --- tiny API helper --------------------------------------------------------

function authToken() {
  return localStorage.getItem("token") || "";
}

// `/media/...` and `/files/...` are the two routes a plain `<img src>` (or a
// note's own inline `![]()` markdown, rendered straight into an `<img>` tag)
// points at directly: a declarative resource load never attaches the
// X-Auth-Token header the way `apiJson`/`fetch` calls here do, so every such
// image was a silent 401 (an empty/broken image, nothing thrown, nothing
// logged, `isRenderableUrl` already having confirmed it same-origin) on any
// notebook with a password set, which is the normal case. The backend's
// `require_unlock_media` accepts the media cookie for exactly these two
// prefixes; every other endpoint stays header-only. `mediaSrc` is still the
// one door every such URL goes through (it resolves staged pictures), so
// every call site keeps using it unconditionally.
//: **Declared up here, and the reason is the `SPACE_ALL` story below.** A
//: `const` is in the temporal dead zone until its own line runs, and
//: `mediaSrc` is called during boot, long before the capture composer's own
//: section of this file is reached. Left where they logically belong (beside
//: `handleFileUpload`), the very first render would throw
//: `ReferenceError: Cannot access 'STAGED_URL_PREFIX' before initialization`,
//: which `node --check` cannot see because the file is syntactically perfect.
const STAGED_URL_PREFIX = "staged:";

//: Images waiting for a note to exist, the bytes stay in the browser until
//: Save produces an id. See `handleFileUpload` for the whole arrangement.
let captureStagedImages = [];

function stagedImageByUrl(url) {
  if (typeof url !== "string" || !url.startsWith(STAGED_URL_PREFIX)) return null;
  const key = url.slice(STAGED_URL_PREFIX.length);
  return captureStagedImages.find((image) => image.key === key) || null;
}

//: **The one thing staging must never do: reach the database.**
//:
//: REDESIGN.md §R7.2 held this feature back for a whole session over exactly
//: this failure mode, and the wording is worth keeping: every path that can
//: save the composer has to rewrite the staged markers first, and one that
//: does not leaves `staged:`/`blob:` URLs inside saved note content, 
//: *corrupted notes, which is worse than the recoverable orphan it replaces*
//: (orphans already have a collector; a note whose picture is a dead
//: in-memory key has nothing).
//:
//: That section asked for "a test per save path". This is the stronger
//: version of the same idea and the reason there is no allowlist of save
//: paths anywhere: rather than enumerate the functions that must remember to
//: call `rewriteStagedUrls`, an enumeration a future save path joins by
//: being forgotten: every request in the app passes through `api()`, so the
//: check lives there and a new save path is covered by existing.
//:
//: It throws rather than repairing. A silent fix would hide the bug and ship
//: a note missing its picture; a throw surfaces in the caller's own error
//: toast with the note still unsaved in the box, so nothing is lost.
//:
//: Matched on the markdown embed shape, not on the bare scheme: a note that
//: happens to contain the word "staged:" is ordinary prose, while `](staged:`
//: is a link target this app wrote and never a sentence a person typed.
const STAGED_IN_BODY = /]\((?:staged|blob):/;

function refuseStagedUrls(body) {
  if (typeof body !== "string" || !STAGED_IN_BODY.test(body)) return;
  throw new Error(
    "That still holds an image that hasn't finished uploading: try saving again in a moment."
  );
}

//: **A mouse wheel's ctrl+notch zooms by a notch, not by five times.** d3-zoom
//: multiplies a wheel delta by ten while ctrl is held, because a browser
//: reports a trackpad pinch as ctrl+wheel with deltas of a few pixels. A mouse
//: wheel notch with ctrl held sends 100 to 120 of them and so got 2^2.4, a
//: factor of 5.3: two notches took a map from 1x to its 4x ceiling
//: (maprender.md measured it; unreported, but the likeliest reading of a zoom
//: that "jumps" on a machine with a real mouse). The delta is clamped to 24
//: pixels while ctrl is held (a notch is then 1.4x; a pinch is a few pixels
//: an event and passes through unchanged), then scaled exactly as d3's own
//: default scales it, so a plain wheel and a pinch zoom as they did.
function zoomWheelDelta(event) {
  let pixels = event.deltaY * (event.deltaMode === 1 ? 25 : event.deltaMode ? 500 : 1);
  if (event.ctrlKey) pixels = Math.max(-24, Math.min(24, pixels));
  return -pixels * 0.002 * (event.ctrlKey ? 10 : 1);
}

function mediaSrc(url) {
  //: A staged picture has no server url yet; its bytes are a Blob in this
  //: tab. Resolved here rather than at each `<img>` so every surface that
  //: renders note markdown, the composer preview, the live view, a widget , 
  //: shows it without knowing staging exists.
  if (typeof url === "string" && url.startsWith(STAGED_URL_PREFIX)) {
    return stagedImageByUrl(url)?.objectUrl || url;
  }
  //: **No credential goes in the URL** (WORLD_CLASS_PLAN §12, S1). This used
  //: to append the session token as a query parameter, which put the key to
  //: the whole notebook into history, the server's access log and any note an
  //: image address was pasted into. The media cookie the server sets at
  //: unlock (`MEDIA_COOKIE`, routes_auth.py) rides along on these loads by
  //: itself, opens `/media` and `/files` only, and no script can read it;
  //: `refreshMediaSession` (shell-reminders.js) re-asks for it when a token is restored.
  return url;
}

//: The media cookie for a token this tab already holds: called on the boot
//: path before anything renders a picture, because a profile that kept the
//: token in localStorage may have lost its cookies (cleared site data, a
//: browser that drops them on exit). Unlock, setup and a password change set
//: the cookie in their own responses, so they never need this. Never throws:
//: a failure here is a broken picture, not a broken boot, and the first
//: locked request will show the lock screen anyway if the token is stale.

// **A file that is no longer there should say so, not draw a broken frame.**
//
// Reported with a screenshot of a timeline popup: "a photo i attached to a
// note ages ago but deleted still randomly shows itself as a placeholder
// empty image with the image filename". A note's body keeps the
// `![name](/media/…)` markdown it was written with, so deleting the upload
// leaves a live `<img>` pointing at a 404, and what a browser draws for that
// is its own torn-page glyph beside the alt text, which is the filename. It
// looks like the app is broken rather than like the file is gone.
//
// One delegated listener rather than an `onerror` at each of the twenty-odd
// places that build an `<img>`: `error` does not bubble, but it *does*
// capture, so a single capturing listener on the document sees every image
// failure in the app, including the ones inside rendered markdown, which no
// call site here constructs and could not have been given a handler anyway.
//
// The note's text is deliberately left alone. Rewriting a person's own words
// because a file they referenced is missing is a bigger claim than this
// evidence supports (a media route can 404 for a locked notebook or a
// half-finished restore too), and it is not reversible. This says what is
// true, there was an image here and it is not available, in the app's own
// materials, and leaves the source as the record.
function replaceMissingMedia(img) {
  const src = img.getAttribute("src") || "";
  // Only this app's own stored files. An external image that fails is a
  // different situation, and the note may well want it back when the network
  // returns.
  if (!/^\/(media|files)\//.test(src)) return;
  //: **An image the app addresses by id is hidden, never replaced.** This
  //: listener was written for the images inside rendered markdown, which are
  //: built fresh on every render and referred to by nobody: swapping one for a
  //: placeholder costs nothing. `#ocr-image` is the opposite: one long-lived
  //: element that the OCR workspace sets a new `src` on for every page of
  //: every document it opens.
  //:
  //: Measured. Opening a text file (a .md attachment) in the workspace sets
  //: `img.src` to that file's own url before the text branch of `ocrLoadPage`
  //: runs, the browser cannot decode markdown as an image, this listener fired
  //: and `img.replaceWith(gone)` deleted `#ocr-image` from the document. After
  //: that the stage held `SPAN.media-missing` and no `<img>` at all, for the
  //: rest of the session: every later open threw "Cannot set properties of
  //: null (setting 'src')" at `ocrLoadPage`, so clicking the next file's name
  //: opened a workspace that never showed the page. CLAUDE.md's own shape: the
  //: damage lands nowhere near the code that caused it.
  //:
  //: Hidden rather than replaced, so nothing draws a torn-page glyph and the
  //: element the app is holding on to is still there. The surfaces that own
  //: such an image say what happened in their own words (`#ocr-message`), and
  //: they unhide it themselves the moment a page really loads.
  if (img.id) {
    img.classList.add("hidden");
    return;
  }
  //: **A thumbnail is hidden too.** A picture beside a row's own words (the
  //: dashboard's recent notes, the Contents index, a chat source, a
  //: timeline row: every class here ending in `-thumb`) is a hint, and the
  //: words beside it already name the thing. The placeholder, a 170px dashed
  //: box of "Image no longer in this notebook", was drawn into a 2.5rem slot
  //: and pushed the row's title off its column (measured on the dashboard's
  //: Recently added and the Contents index). An attachment's own thumbnail is
  //: the exception: it is the attachment, so saying it is gone is the point.
  if (/-thumb\b/.test(img.className) && !img.classList.contains("attachment-thumb")) {
    img.classList.add("hidden");
    return;
  }
  if (img.dataset.mediaMissing) return;
  img.dataset.mediaMissing = "1";
  const gone = document.createElement("span");
  gone.className = "media-missing";
  const name = (img.getAttribute("alt") || "").trim();
  setLabel(gone, `ph:image-broken ${name || "Image"}`);
  const note = document.createElement("span");
  note.className = "media-missing-note";
  note.textContent = "no longer in this notebook";
  gone.append(note);
  gone.title = `${name || "This image"} was removed. The note still mentions it.`;
  img.replaceWith(gone);
}

//: **After the image's own handler, never before it.** A capturing listener
//: on the document runs ahead of every listener on the image itself, so an
//: image that had its own answer to a failure (a Library file tile's first
//: page, which removes itself and leaves the file glyph underneath) was
//: already swapped for "Image no longer in this notebook" by the time its
//: own handler ran, and that handler then removed a detached element.
//: Measured on the Files sub-tab: the placeholder drawn inside all three PDF
//: tiles, under the tick. A task later, an image its owner removed (or whose
//: tile its owner removed) is no longer connected, and is left alone.
document.addEventListener(
  "error",
  (event) => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement)) return;
    setTimeout(() => {
      if (img.isConnected) replaceMissingMedia(img);
    }, 0);
  },
  true,
);

// A page-load-order bug lived here: this was declared down in the spaces
// section (appended at the end of the file), and `api()`, called from
// `initAuth()` at module load, long before that point in the script runs, 
// reads it via `activeSpaceId()` on every request's headers below. A `const`
// is in the temporal dead zone until its own declaration executes, so the
// very first request the app ever made threw `ReferenceError: Cannot access
// 'SPACE_ALL' before initialization`, caught by api()'s own try/catch and
// surfaced only as "Can't reach the Tessellate server", the lock screen
// never appeared, with no console error and no failed network request,
// because the fetch was never reached. `node --check` cannot catch this: the
// file is syntactically valid, only wrong in execution order. Declared here,
// before `api()` is ever callable, so this cannot happen again regardless of
// what gets appended below.
const SPACE_ALL = "all";

//: Here and not with the spaces code: `api()` calls it on every request, and
//: the first one is made at load, before spaces-find.js (a later classic
//: script) has run ("activeSpaceId is not defined" on GET /health). prefs.js
//: also loads after this file, so its absence reads as the default space.
function activeSpaceId() {
  return (typeof prefs !== "undefined" && prefs.get("spaceId", null)) || SPACE_ALL;
}

async function api(path, options = {}) {
  // `silent`: a background poll (model status, reminders): a 401 must not
  // yank the user to the lock screen mid-session (Wave O fix for a
  // long-standing intermittent re-lock). Only an explicit user action
  // shows the lock screen on 401.
  // `timeoutMs`: opt-in abort so a call can't hang the UI forever (used by the
  // startup probe). Off by default, so long-running requests, model pulls,
  // blocking chat: are unaffected.
  // `ownsAuthErrors`: this call treats 401 as part of its own result rather
  // than as an expired session. Change-password answers 401 for "that isn't
  // your current password", a typo there must show a message beside the
  // field, not throw the user out to the lock screen.
  // `readOnly`: a POST that writes nothing (the code checker in documents.js
  // sends a file's text in a body because a query string cannot carry it).
  // Without it every pause in typing a .py file would empty the read cache
  // for the whole app, which is a write's job, not a read's.
  const { silent, timeoutMs, ownsAuthErrors, readOnly, ...fetchOptions } = options;
  refuseStagedUrls(fetchOptions.body);
  // Any write invalidates the read cache above, see clearApiCache().
  if (!readOnly && fetchOptions.method && fetchOptions.method !== "GET") clearApiCache();
  let timer = null;
  if (timeoutMs) {
    const controller = new AbortController();
    timer = setTimeout(() => controller.abort(), timeoutMs);
    fetchOptions.signal = fetchOptions.signal || controller.signal;
  }
  let response;
  //: Rule 4: a network-level failure of a read (GET, HEAD) retries itself
  //: twice, 300 then 600 ms apart, before anything is said; `api.retries`
  //: counts them. A write is never resent: it may have arrived.
  for (let attempt = 0; ; attempt++) try {
    response = await fetch(path, {
      ...fetchOptions,
      headers: {
        ...(fetchOptions.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        "X-Auth-Token": authToken(),
        // Which space this request is scoped to. The server reads it in
        // get_session() and adds a loader criterion for it, so leaving it off
        // means every request silently sees every space, the switcher would
        // change the label in the header and nothing else.
        "X-Workspace-ID": activeSpaceId(),
        ...fetchOptions.headers,
      },
    });
    break;
  } catch (networkErr) {
    if (attempt < 2 && networkErr instanceof TypeError && /^(GET|HEAD)$/.test(fetchOptions.method || "GET")) {
      api.retries++;
      await new Promise((r) => setTimeout(r, 300 * (attempt + 1)));
      continue;
    }
    // fetch() itself threw: this is a real network failure (offline, CORS,
    // connection refused). Log it explicitly so it always appears in Logs.
    //: A timeout (`AbortSignal.timeout`, name "TimeoutError") is a slow
    //: answer, not a failure: a warning, and for a silent poll (the model
    //: status, which shows "slow" and asks again) not even that.
    if (networkErr?.name !== "AbortError" && !(silent && networkErr?.name === "TimeoutError")) {
      recordBrowserLog(networkErr?.name === "TimeoutError" ? "WARN" : "ERROR", [
        `[Network] ${fetchOptions.method || 'GET'} ${path}: ${networkErr.message}`
      ]);
    }
    //: **The backend is not there to answer, not just this one request.**
    //: A `TimeoutError` is a slow answer (see the comment above), not proof
    //: the server is down, so it does not raise the banner; every other
    //: `fetch()` throw here (connection refused, DNS failure, offline) does.
    //: `noteServerDown` (status.js) is idempotent, so the dozen requests a
    //: busy tab fires while the server is stopped raise one banner, not
    //: twelve.
    if (networkErr?.name !== "AbortError" && networkErr?.name !== "TimeoutError") {
      noteServerDown();
    }
    //: "Failed to fetch" and its kin go to the log above; the toast gets a sentence.
    if (networkErr instanceof TypeError) networkErr.message = "Tessellate is not answering. Is it still running?";
    throw networkErr;
  } finally {
    if (timer) clearTimeout(timer);
  }
  //: `fetch()` returned at all, so whatever HTTP status came back, the
  //: server answered: the fastest sign it is back after being down, ahead of
  //: the retry poll's own backoff.
  noteServerUp();
  if (response.status === 401 && !ownsAuthErrors) {
    //: A silent read stays quiet, but a silent write (a setting changed after
    //: the server restarted) got "Locked" in a toast with no lock screen.
    if (!silent || fetchOptions.method) showLockScreen(false); // token expired (e.g. app restarted)
    const locked = new Error("Locked");
    // Marked, so `startApp()`'s bootstrap loop can tell "the session expired"
    // apart from "this one endpoint failed". Reported: *"before signing in, a
    // popup shows a message saying failed to load entries"*, a stale token
    // in localStorage (server restarted since the last visit) makes `startApp`
    // fire a dozen requests in parallel before the user has unlocked
    // anything, every one of them hits this 401, and every one of them used
    // to toast its own "Couldn't load X: Locked" on top of the lock screen
    // that had already, correctly, just appeared. One state: not logged in
    //, was being reported as a dozen unrelated failures.
    locked.isLockout = true;
    throw locked;
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const rawMsg = typeof detail.detail === 'string' ? detail.detail : JSON.stringify(detail.detail);
    let errMsg = plainHttpError(response.status, detail.detail);
    //: **Out of space is the one failure the person can act on, so the part
    //: that says how travels with it.** The server answers 507 with a
    //: `hint` naming the folder, the room left and roughly how much to free
    //: up (INBOX 266, item 6); every call site in this app toasts
    //: `error.message` and nothing has ever read `hint`, so the actionable
    //: half was being thrown away at this line. Appended here rather than
    //: at fifty call sites, which is the only version that cannot be
    //: forgotten by the next one.
    if (response.status === 507 && typeof detail.hint === 'string' && detail.hint) {
      errMsg = `${errMsg} ${detail.hint}`;
    }
    if (!silent) {
      // Log HTTP errors so they always appear in Settings → Logs for debugging.
      recordBrowserLog("ERROR", [
        `[HTTP ${response.status}] ${fetchOptions.method || 'GET'} ${path}: ${rawMsg}`
      ]);
    }
    //: The status and the structured detail travel on the error, so a
    //: caller that has something to do with a particular refusal (an edit
    //: conflict's 409 carries the text another window saved,
    //: `editConflictPrompt`) can read it rather than parse a message.
    const error = new Error(errMsg);
    error.status = response.status;
    if (response.status < 500) toast.refused.add(errMsg);
    error.detail = detail.detail;
    error.body = detail;
    throw error;
  }
  //: A write that can leave a model running on a background thread gets the
  //: task poll looked at now, rather than up to ten seconds from now.
  //:
  //: Reported as *"notifications dont appear when generating image
  //: captions"*, and the cause is a cadence, not a missing notification.
  //: `refreshModelStatus` idles at 10s (120s behind a hidden tab), and
  //: `noticeTaskTransitions` can only announce a job it has actually *seen*
  //: in a `/tasks` payload. A caption is one model round-trip, often
  //: shorter than the gap between two idle polls, so it began and ended
  //: unobserved: no "Started" line, no status-bar job slot, nothing. The
  //: long jobs this panel was built for (a re-index, a model pull) never hit
  //: this because they outlive any poll interval.
  if (fetchOptions.method && fetchOptions.method !== "GET" && JOB_STARTING_PATH.test(path)) {
    kickBackgroundTaskPoll();
  }
  return response;
}
api.retries = 0;
// F5 (tests/test_no_bare_fetch.py)
api.upload = (path, body, options) => api(path, { method: "POST", body, ...options });
api.stream = api;

// --- reading a paged list endpoint whole ---------------------------------------
//
// `GET /documents`, `GET /media`, `GET /reminders` and the rest each return a
// page and an `X-Total-Count` header saying how big the selection really is
// (INBOX 117; `GET /entries` has worked this way for longer, see
// `loadEntries`). A caller that needs every row asks for the next page until it
// has them all, which is the half that makes a cap safe: a cap with no offset
// makes everything past it permanently unreachable, and that is exactly the
// failure the old uncapped list was avoiding.
//
// **It lives here, immediately below `api()`, and that placement is the whole
// of a crash report.** It used to live in documents.js, whose own comment
// argued that "both call it from inside a function body, so load order is
// satisfied either way". That stopped being true the moment app.js called it
// from boot code: index.html loads app.js first and documents.js ten lines
// later, so `initNotesSubtabs` running at the bottom of this file reached a
// function that did not exist yet, and the Notes tab died with
// `ReferenceError: apiPagedList is not defined` before it drew anything. Six
// frontend files call this now; the file every one of them is loaded after is
// this one. `tests/test_frontend_load_order.py` is the rule, so the next
// shared helper cannot be put somewhere only some callers can see.
//
// `options` is passed through to `api()` untouched (library.js wants
// `{ silent: true }`). A page that comes back empty ends the loop whatever the
// header says, so a stale or wrong total can never spin forever.
async function apiPagedList(path, pageSize, options = {}) {
  const rows = [];
  let total = Infinity; // discovered from the first response's X-Total-Count
  while (rows.length < total) {
    const joiner = path.includes("?") ? "&" : "?";
    const response = await api(`${path}${joiner}limit=${pageSize}&offset=${rows.length}`, options);
    const page = await response.json();
    if (!Array.isArray(page) || !page.length) break;
    rows.push(...page);
    const reported = Number(response.headers.get("X-Total-Count"));
    total = Number.isFinite(reported) && reported > 0 ? reported : rows.length;
  }
  return rows;
}


//: Paths whose response can leave captioning, OCR or a librarian pass running
//: on a background thread. Deliberately a short list rather than "every
//: write": filing a note or a message is exactly when an attached image
//: starts being read (`core/media_process.py` runs at *commit*, not at
//: upload), but a rename or a preference save can start nothing and should
//: not cost a poll.
const JOB_STARTING_PATH =
  /^\/(entries|documents|media\/upload|media\/\d+\/|files\/\d+\/|conversations\/\d+\/messages|extras\/|models\/pull|search\/reindex|tasks\/trigger-autonomous)/;

//: Debounced, because committing a note with four images is four writes and
//: one job list. 600ms rather than immediately: the thread is started after
//: the response is written, so a poll racing it by a millisecond sees the
//: state from just before the job existed, the exact miss this fixes.
let jobPollKick = null;
function kickBackgroundTaskPoll() {
  //: A write that starts a job is the clearest "something just changed"
  //: there is, so the status poll's idle backoff (see `resetStatusCadence`)
  //: starts again from 30s rather than the job's progress being reported on
  //: a two-minute delay. Reached only from `api()` on a non-GET, which
  //: cannot happen before this file has finished evaluating, so the `const`
  //: that function reads is always past its temporal dead zone by then.
  resetStatusCadence();
  clearTimeout(jobPollKick);
  jobPollKick = setTimeout(() => {
    refreshBackgroundTasks().catch(() => {
      // A poll is best-effort, it runs again on the status loop regardless.
    });
  }, 600);
}

// A short-lived cache for GET responses, opt-in per call.
//
// Every dashboard widget fetches its own data, and switching away from the
// Dashboard and back re-ran all of them against data that is, in practice,
// seconds old: a network round trip and a re-render for nothing new to
// show. Opt-in (`cacheMs`) rather than global: silently serving a stale
// answer to something that must be current the instant it changes (reminder
// due-times, model status) would be a worse bug than the one this fixes.
//
// Invalidated wholesale by any mutating request (see `api()` below) rather
// than tracked per-endpoint: simpler, and correct: the common case this
// exists for is "nothing changed since I was last on this tab", and any
// write at all means that's no longer true.
const _apiCache = new Map();

function clearApiCache() {
  _apiCache.clear();
}

async function apiJson(path, options = {}) {
  const { cacheMs, ...rest } = options;
  if (cacheMs && (!rest.method || rest.method === "GET")) {
    const hit = _apiCache.get(path);
    if (hit && Date.now() - hit.at < cacheMs) return hit.pending || hit.data;
    //: **A request already in flight is shared, not repeated.** Measured at
    //: boot (`scratchpad/ui-sweeps/oi-dupfetch.js`): the Notes tab's "Ask
    //: again" row and the dashboard's Recent questions widget both asked for
    //: `/chat/recent` within the same second, and the same for
    //: `/entries/most-accessed`, because the second caller arrived before the
    //: first answer did and the cache only held finished answers. The promise
    //: is cached with the entry and replaced by the data when it lands; a
    //: failure is dropped from the cache so the next caller asks again.
    const pending = api(path, rest).then((response) => response.json());
    const entry = { pending, at: Date.now() };
    _apiCache.set(path, entry);
    try {
      const data = await pending;
      if (_apiCache.get(path) === entry) _apiCache.set(path, { data, at: entry.at });
      return data;
    } catch (error) {
      if (_apiCache.get(path) === entry) _apiCache.delete(path);
      throw error;
    }
  }
  const data = await (await api(path, options)).json();
  //: A new note is a small event worth a cheer from the companion, and a
  //: proud look from Atlas (atlas.js).
  if (path === "/entries" && options.method === "POST") {
    if (typeof nameMarkBuddyCue === "function") nameMarkBuddyCue("carry");
    if (typeof atlasOn === "function") atlasOn("saved");
  }
  return data;
}

// --- auth gate (Phase 4) -----------------------------------------------------

//: **Optional sign-in** (INBOX 426 aa): "Ask for a password when the app
//: opens", a switch in Settings, Account and security. Off, the server hands
//: this computer a session without the password (`/auth/auto-session`,
//: routes_auth.py, which decides from the connection itself and refuses
//: anyone else), and the boot path skips the lock screen. The vault is not
//: opened by that: private notes ask for the password when they are wanted,
//: through the lock screen's own card in a prompt mode (`askPasswordPrompt`).
//:
//: `autoSessionOffered`: `/auth/status` said this caller may have one.
//: `lockedByHand`: the person pressed Lock, so a 401 afterwards must not
//: quietly start a new session; the next load does (the decision taken).
//: `vaultOpen`: null until an unlock, the auto-session or the account
//: answer says; false only when it is known to be locked.
let autoSessionOffered = false;
let lockedByHand = false;
let vaultOpen = null;
let autoSessionPending = null;
//: The open prompt: `{ submit, resolve, returnFocus }`, or null.
let lockPrompt = null;

//: Ask the server for a session without a password. One request at a time,
//: because a stale token makes every boot request answer 401 together.
//: Plain `fetch`, not `api()`: a refusal here is an answer, not a lockout.
function startWithoutPassword() {
  if (!autoSessionPending) {
    autoSessionPending = fetch("/auth/auto-session", {
      method: "POST",
      headers: { "X-Auth-Token": authToken() },
    })
      .then((response) => (response.ok ? response.json() : null))
      .catch(() => null)
      .finally(() => {
        autoSessionPending = null;
      });
  }
  return autoSessionPending;
}

function enterWithoutPassword(body) {
  localStorage.setItem("token", body.token);
  vaultOpen = Boolean(body.vault_open);
  lockedByHand = false;
  const opening = startApp();
  curtainShell(opening);
}

//: A session that expired while sign-in is off comes straight back rather
//: than asking for a password the person chose not to be asked for.
async function resumeWithoutPassword() {
  const body = await startWithoutPassword();
  if (!body) {
    autoSessionOffered = false; // refused: the lock screen stays, as it should
    return;
  }
  if ($("lock-overlay").dataset.mode !== "unlock") return; // setup or a prompt since
  enterWithoutPassword(body);
}

//: Close the prompt, if one is open. `done` is what its promise resolves to.
function settleLockPrompt(done) {
  const prompt = lockPrompt;
  if (!prompt) return;
  lockPrompt = null;
  const overlay = $("lock-overlay");
  overlay.classList.remove("lock-prompt");
  $("lock-cancel").classList.add("hidden");
  $("lock-error").textContent = "";
  $("lock-password").value = "";
  if (overlay.dataset.mode === "prompt") {
    overlay.classList.add("hidden");
    overlay.dataset.mode = "unlock";
    prompt.returnFocus?.focus?.();
  }
  prompt.resolve(done);
}

//: The lock screen's card asking for the password for one action, over
//: whatever is open, with a way out. `submit(password)` throws to show its
//: message under the field. `data-mode="prompt"` is set before the overlay
//: is shown: the document editor's lock watcher (documents.js) reads it, and
//: a prompt is not a lock.
function askPasswordPrompt({ title, message, submitLabel, submit }) {
  settleLockPrompt(false);
  const overlay = $("lock-overlay");
  return new Promise((resolve) => {
    lockPrompt = { submit, resolve, returnFocus: document.activeElement };
    overlay.dataset.mode = "prompt";
    overlay.classList.add("lock-prompt");
    $("lock-title").textContent = title;
    $("lock-message").textContent = message;
    $("lock-setup-note")?.classList.add("hidden");
    $("lock-submit").textContent = submitLabel;
    $("lock-cancel").classList.remove("hidden");
    $("lock-error").textContent = "";
    $("lock-password").value = "";
    $("lock-password").setAttribute("type", "password");
    $("lock-password").setAttribute("aria-label", "Password");
    $("lock-password").placeholder = "Password"; // a prompt never takes the PIN
    $("lock-password").autocomplete = "current-password";
    overlay.classList.remove("hidden");
    $("lock-password").focus();
  });
}

//: Modal dialogs and popovers sit in the top layer, above the lock screen,
//: and make it inert: a lock left them readable and the password field
//: untypeable. They are put away while it shows and back, as they were,
//: after it, so a half-written dialog loses nothing.
let lockStash = [];
new MutationObserver(() => {
  if ($("lock-overlay").classList.contains("hidden")) {
    for (const el of lockStash) {
      try { if (el.isConnected) el.popover ? el.showPopover() : el.showModal(); } catch { /* reopened meanwhile */ }
    }
    lockStash = [];
  } else {
    for (const el of document.querySelectorAll("dialog:modal, :popover-open")) {
      lockStash.push(el);
      el.popover ? el.hidePopover() : el.close();
    }
  }
}).observe($("lock-overlay"), { attributes: true, attributeFilter: ["class"] });

function showLockScreen(setupMode) {
  settleLockPrompt(false);
  $("lock-overlay").classList.remove("hidden");
  $("lock-title").textContent = setupMode ? "Welcome to Tessellate" : "Unlock Tessellate";
  //: **The trust moment, and it used to say nothing about trust.** This is the
  //: first screen of the app and it asks for a credential; a person deciding
  //: whether to hand one over is deciding whether to believe the product, and
  //: the sentence that would persuade them ("it runs here, nothing goes out")
  //: was three screens later, after the account already existed. It is here
  //: now, along with the two facts that cost something to learn late: the
  //: length rule, which was only ever shown after a failed attempt, and that
  //: `/auth/setup` derives an encryption key from this password on the spot.
  $("lock-message").textContent = setupMode
    ? "A notebook that runs on this machine. Your notes stay here, and nothing goes online unless you turn it on later."
    : "Enter your password to unlock your notebook.";
  //: Four is the backend's own floor (`Field(min_length=4)`,
  //: routes_auth.py), quoted rather than restated so the two cannot drift.
  const note = $("lock-setup-note");
  if (note) {
    note.textContent =
      "Choose a password, at least eight characters; a few unrelated words are best. The app asks for it " +
      "when it opens, unless you turn that off in Settings. Ordinary notes are not encrypted and survive a reset, " +
      "but anything you later mark private is locked with this password and cannot " +
      "be recovered without it.";
    note.classList.toggle("hidden", !setupMode);
  }
  $("lock-submit").textContent = setupMode ? "Set password & start" : "Unlock";
  $("lock-overlay").dataset.mode = setupMode ? "setup" : "unlock";
  lockFieldForPin(setupMode ? false : pinHere);
  // One field in two modes (no separate setup form), autocomplete has to
  // switch with it, or a password manager offers to fill an *existing*
  // saved password into a first-run "choose a new one" field.
  if (setupMode) $("lock-password").setAttribute("aria-label", "Choose a password");
  $("lock-password").autocomplete = setupMode ? "new-password" : "current-password";
  $("lock-password").focus();
  if (!setupMode && autoSessionOffered && !lockedByHand) resumeWithoutPassword();
  //: A PIN set or forgotten since the last look (Settings, or five wrong
  //: tries) changes what the field asks for, so the lock asks again.
  if (!setupMode) {
    apiJson("/auth/status", { silent: true })
      .then((status) => {
        pinHere = Boolean(status?.pin_here);
        if ($("lock-overlay").dataset.mode === "unlock") lockFieldForPin(pinHere);
      })
      .catch(() => {});
  }
}

//: Owner, 2026-10-12: "Password", or "PIN or password" only where a PIN is
//: set on this computer (`/auth/status` `pin_here`, which is False for any
//: other device). One field takes either; the server tries the password
//: first and the PIN only from this computer.
let pinHere = false;
function lockFieldForPin(pin) {
  const label = pin ? "PIN or password" : "Password";
  $("lock-password").placeholder = label;
  $("lock-password").setAttribute("aria-label", label);
  if ($("lock-overlay").dataset.mode === "unlock") {
    $("lock-message").textContent = pin
      ? "Enter your PIN or password to unlock your notebook."
      : "Enter your password to unlock your notebook.";
  }
}

//: **The containers that hold the user's own words**, cleared when the
//: notebook locks. Enumerated explicitly rather than derived, because this is
//: a privacy boundary and a reviewer should be able to read exactly what is
//: purged without running anything.
//:
//: Static UI text (the Settings panels, the capture form's own labels) is
//: deliberately not here: it belongs to the app, not to the user, and
//: clearing markup that `startApp()` does not rebuild would break the app on
//: unlock.
const LOCK_PURGE_IDS = [
  "entry-list", // notes
  "chat-messages", // the conversation
  "library-grid", // files and images
  "library-docs-list", // documents
  "timeline-feed", // the timeline
  "timeline-table-body",
  "reminder-groups", // reminders
  "timeline-calendar",
  "graph-svg", // node labels are note titles
  "palette-list", // whatever was last searched for
  "palette-preview", // and the note it was showing
  "doc-live",
  "doc-preview",
];

//: Empty everything the lock screen is covering.
//:
//: **The lock overlay was a visual cover, not a purge**, and the roadmap
//: ranked auditing it first precisely because it is this app's only privacy
//: boundary. Measured with the notebook locked: `#entry-list` still held 61
//: notes and 3,431 characters of their text, `#library-grid` 5,089, the
//: documents list 6,422: all of it one devtools click, one screen reader,
//: or one browser extension away from being read.
//:
//: The server side was already right (every endpoint answers 401 while
//: locked, verified in the same audit), so this closes the client half.
//:
//: Safe because unlocking runs `startApp()`, which re-fetches and re-renders
//: all of it. The codebase already reasons this way elsewhere, 
//: `hideBootSplash` removes itself from the DOM rather than leaving a hidden
//: overlay, on the same principle that nothing should sit over the viewport
//: invisibly.
function purgeLockedContent() {
  for (const id of LOCK_PURGE_IDS) {
    const el = document.getElementById(id);
    if (el) el.replaceChildren();
  }
  // A textarea's text lives in `.value`, which `replaceChildren` never
  // touches: the document editor would otherwise keep the whole document
  // readable behind the lock screen.
  for (const id of ["doc-content", "doc-title", "entry-input", "chat-input"]) {
    const field = document.getElementById(id);
    if (field && "value" in field) field.value = "";
  }
}

async function lockNow() {
  try {
    await api("/auth/lock", { method: "POST" });
  } catch {
    /* locking locally regardless */
  }
  localStorage.removeItem("token");
  lockedByHand = true;
  vaultOpen = false;
  purgeLockedContent();
  showLockScreen(false);
}

// Fades out and removes #boot-splash (index.html): called once, from
// initAuth() below, the moment its /auth/status round trip resolves,
// whichever of that function's four branches it turns out to be. Removed
// from the DOM after the fade rather than left `hidden`: nothing should
// keep sitting fixed over the whole viewport, even invisibly, once the app
// has decided what it's actually showing.
//:
//: **It fades; it used to cut** (INBOX 577). The class was `hidden`, whose
//: `display: none !important` (02-chat-graph.css) beat the splash's own
//: opacity rule, so the fade written for it never ran and `transitionend`
//: never came: the splash vanished between two frames and stayed in the DOM
//: for good (measured: still there, `display: none`, after every boot). Its
//: own leaving class, and a timer behind the event.
function hideBootSplash() {
  const splash = document.getElementById("boot-splash");
  if (!splash || splash.classList.contains("boot-splash-leaving")) return;
  // Snap the bar to 100% before the fade starts, so it never visibly
  // disappears mid-crawl: it always reads as "finished", never "cut off".
  document.getElementById("boot-splash-progress-fill")?.classList.add("done");
  splash.classList.add("boot-splash-leaving");
  const gone = () => splash.remove();
  splash.addEventListener("transitionend", gone, { once: true });
  // Reduced motion strips the transition, so transitionend never fires.
  setTimeout(gone, reducedMotionWanted() ? 0 : 400);
}

async function initAuth() {
  // Bounded probe: if the server is unreachable or hangs, fail fast with a
  // clear message instead of an indefinite blank/"connecting" screen.
  const status = await apiJson("/auth/status", { timeoutMs: 8000 }).catch(() => null);
  //: The splash goes now only where the app is not about to start under it:
  //: a start lifts it with the shell (`curtainShell`).
  if (!status || status.setup_required || (!status.auto_session && !authToken())) hideBootSplash();
  if (!status) {
    $("save-status").textContent = "Can't reach the Tessellate server. Is it running?";
    toast("Can't reach the Tessellate server. Is it running?", true, { action: ["Reload", () => location.reload()] });
    return;
  }
  if (status.setup_required) {
    showLockScreen(true);
    return;
  }
  $("lock-btn").classList.remove("hidden");
  pinHere = Boolean(status.pin_here);
  // Sign-in off, on this computer: straight in, no lock screen. A token
  // still live is kept by the server; a stale one is replaced.
  autoSessionOffered = Boolean(status.auto_session);
  if (autoSessionOffered) {
    const started = await startWithoutPassword();
    if (started) {
      enterWithoutPassword(started);
      return;
    }
    autoSessionOffered = false;
  }
  if (!authToken()) {
    hideBootSplash();
    showLockScreen(false);
    return;
  }
  // Token might be stale after a server restart, startApp()'s first
  // request will bounce us to the lock screen if so. The media cookie first,
  // awaited, so the first pictures the app draws already carry it: one local
  // round trip, and without it a profile that lost its cookies drew every
  // picture broken (see `refreshMediaSession`).
  if (!(await refreshMediaSession())) {
    hideBootSplash();
    showLockScreen(false);
    return;
  }
  const opening = startApp();
  curtainShell(opening);
}

function startApp() {
  // Whatever the shell was last saying about being unable to reach the server
  // is now provably false, we are about to talk to it. Left uncleared, the
  // "check it's running, then refresh" line sat under the capture form for the
  // whole session after one slow start, telling the user the app was broken
  // while it worked perfectly. Screenshotted.
  const shellStatus = $("save-status");
  if (shellStatus) shellStatus.textContent = "";
  // Warm the filing model, retry stand-ins (routes_models.warm_filing).
  api("/models/warm-filing", { method: "POST", silent: true }).catch(() => {});
  // The notebook file's quick check at start: silent when it passed.
  apiJson("/backups/integrity", { silent: true }).then(noteDamagedNotebook).catch(() => {});

  // The desktop window's own title bar already shows the app's icon, so the
  // header's logo tile under it is the same mark twice (INBOX 705). The server
  // says whether this page runs in that window (`window_hook`, the same
  // answer the documents full screen asks); the answer is kept on this
  // device so the next launch paints without the tile, rather than drawing
  // it and pulling it back when the reply lands. A browser tab keeps it.
  document.documentElement.dataset.chrome = prefs.get("windowChrome", "");
  apiJson("/desktop/fullscreen", { silent: true })
    .then((state) => {
      const chrome = state?.available ? "native" : "";
      document.documentElement.dataset.chrome = chrome;
      prefs.set("windowChrome", chrome);
    })
    .catch(() => {});

  // A failed load must be visible, not a silently empty page, and one
  // broken endpoint must never stop the rest of the app from coming up.
  // Every bootstrap step is isolated so a single rejection surfaces a toast
  // instead of leaving the user staring at a half-loaded (or blank) app.
  const step = (label, fn) => {
    try {
      const result = fn();
      if (result && typeof result.catch === "function") {
        return result.catch((error) => {
          // The lock screen already said what happened; a toast under it
          // repeating "Couldn't X: Locked" for every parallel step is noise
          // about one state dressed up as several failures.
          if (!error.isLockout) toast(`Couldn't ${label}: ${error.message}`, true);
        });
      }
      return Promise.resolve(result);
    } catch (error) {
      if (!error.isLockout) toast(`Couldn't ${label}: ${error.message}`, true);
      return Promise.resolve();
    }
  };

  // Before anything reads a stored setting: bring back whatever this browser
  // has lost. A shell that does not keep localStorage, the desktop window is
  // the reported one (§35E): starts every launch with the default theme and
  // an onboarding tour it has already been through, because both live there
  // and nowhere else. The server's copy fills the gaps, then the look is
  // re-applied so the app settles into the remembered theme rather than
  // staying on the default it painted a moment ago.
  const looksReady = step("restore your settings", async () => {
    if (!prefsCache) {
      await loadPreferences().catch(() => null);
    }
    const restored = prefsCache ? seedUiStateFromServer(prefsCache.ui_state) : false;
    //: The server has had its say, whether it had anything to say or not, so
    //: mirrored writes may be saved from here on (A2). Set before the repaint
    //: below rather than after it, so a throw in any of those five calls cannot
    //: leave the session unable to back up a setting.
    uiStateSeeded = true;
    // The same repaint a second window does when it pulls a newer look.
    if (restored) applyRestoredLook();
    // A seeded background (microbes, mycelium) started before the
    // preferences arrived grew from the placeholder name; regrow it from the
    // real one. A no-op for every other style and when nothing changed.
    if (typeof bgArtRefreshSeed === "function") bgArtRefreshSeed();
    
    // Always check battery efficient mode regardless of ui_state seeding
    const indicator = $("power-saver-indicator");
    if (indicator) {
      if (prefsCache && prefsCache.battery_efficient_mode) {
        indicator.classList.remove("hidden");
      } else {
        indicator.classList.add("hidden");
      }
    }
    // The bell's own icon reads the mute preference, re-render now that
    // prefsCache actually has it, rather than leaving the pre-load default
    // (unmuted) on screen until the notifications panel happens to be opened.
    renderNotificationBadge();
    // Same reason, for the status bar: the slots the user has turned off are
    // in `prefsCache`, and hiding them here rather than on first paint would
    // mean a visible flash of a bar they chose not to have.
    applyStatusBarSlots();
    applyStatusClock();
  });

  const entriesReady = step("load entries", loadEntries);
  step("load recent questions", loadRecentQuestions);
  step("load ask history badge", loadAskHistoryBadge);
  step("load suggestions", loadSuggestions);
  step("load your most-used items", loadMostUsed);
  const templatesReady = step("load templates", loadTemplates);
  templatesReady.then(() =>
    step("set up chat options", () => {
      personaOptions();
      // Wave G: skills chips + the agent-mode toggle read the
      // same prefsCache that loadTemplates just filled.
      loadChatSkills();
      $("tools-toggle").checked = !prefsCache || prefsCache.tools_enabled !== false;
      renderChatModeSeg();
      renderWebSearchToggle();
    })
  );
  step("load answer-length options", loadResponseModes);
  // Here, not at module level beside initSpaceSwitcher(). The switcher's
  // LISTENERS can be bound before there is a token, nothing about a click
  // handler needs the server, but the LIST cannot: /spaces 401s before
  // unlock, the catch leaves spacesCache empty, and nothing ever asks again.
  // The menu would then offer "All spaces" and nothing else, for the whole
  // session, on every fresh start. This is the same shape as the comment
  // below about switchTab painting from a pile of 401s.
  step("load spaces", loadSpaces);
  //: Only a page opened from the share sheet carries `share_*`; the rest of the
  //: intake is a lazy file (shared-intake.js).
  entriesReady.then(() => step("take what was shared to it", () => /[?&]share_/.test(location.search) && takeSharedIntake()));
  step("tell the server your timezone", reportTimezone);
  // Fires only if the user opted in (Settings -> About); the endpoint itself
  // also checks the preference server-side, but skipping the call here means
  // an opted-out install makes zero network attempts, not a wasted one.
  // After the templates, which is what fills `prefsCache`: run beside them it
  // read null and neither asked nor checked (found 2026-10-05, measured).
  templatesReady.then(() => step("check for an update", () => {
    if (prefsCache && prefsCache.update_choice_made === false) return askUpdateChoiceOnce();
    if (prefsCache && prefsCache.update_check_enabled) return checkForUpdate(true);
  }));
  // Independent of update_check_enabled above, this isn't a network
  // check, it's reporting a fact: start.sh/start.bat already git-pulled a
  // real update before this process even started (their own step 0, no
  // preference gates it either). "Only if the app auto updates though,
  // not every time they login", the endpoint self-clears after one read,
  // so this only ever fires the run right after a real update landed.
  step("check for an update notice", checkForSourceUpdateNotice);
  step("load conversations", loadConversationList);
  step("check the model status", refreshModelStatus);
  // Reminders poll on their own timer once running (see startReminderWatch);
  // starting that here, not at module level, is the other half of the fix
  // described above revealTab("dashboard")'s module-level call: the same
  // pile of pre-auth 401s, one endpoint earlier.
  step("watch reminders", startReminderWatch);

  // Re-render whichever tab is on screen. This used to be switchTab() itself,
  // called at module level before initAuth() has a token, so a tab that
  // fetches its own data painted itself from a pile of 401s and then never
  // tried again. On the dashboard that meant an empty grid until you opened
  // Edit layout and cancelled out of it, which re-ran renderDashboard by hand
  // (user-reported). Now the module-level call is revealTab(), DOM only,
  // no fetch: and this is the one place the real data load happens.
  // *After* the entries land, not alongside them. These two ran concurrently,
  // so on a cold load the dashboard rendered against an `allEntries` that was
  // still `[]` and drew its brand-new-notebook card instead of the widgets, 
  // reported as "the dashboard widgets are missing until I refresh or change
  // tabs". Every tab wants the notes; none of them wants to guess.
  //: The view the address names, when the page was opened on one (a reload,
  //: a bookmark, a pasted link: router.js); it loads its own tab, so the
  //: Dashboard is not loaded under it first.
  const tabReady = entriesReady.then(() => step("load this tab", async () => {
    if (typeof routerRestore === "function" && (await routerRestore())) return;
    return refreshActiveTab();
  }));

  // First-run welcome tour (guarded by localStorage; re-runnable from Help).
  //
  // **After the settings are restored, not alongside them.** This is the
  // second half of the reported "onboarding shows every time": the flag lives
  // in localStorage, so a shell that lost it needs the server's copy back
  // *before* this asks: otherwise the tour opens, the flag arrives a moment
  // later, and the person is welcomed to an app they have used for a month.
  looksReady.then(maybeShowOnboarding);
  //: The desktop's one-time console question lives in onboarding.js; the
  //: bundle is fetched only while the question is still unanswered.
  looksReady.then(() => prefsCache && !prefsCache.console_view_intro_seen && maybeShowConsoleViewIntro());
  //: What the opening curtain waits for (`curtainShell`): the look and the
  //: first tab drawn.
  return Promise.all([looksReady, tabReady]);
}
// The per-tab data loads switchTab performs, without the tab-switching itself.
// Kept beside switchTab's own dispatch so the two can't drift apart.
async function refreshActiveTab() {
  const name = localStorage.getItem("activeTab") || "notes";
  //: The tab on screen may be one whose code arrives on demand (A1), and this
  //: is the boot-time call that loads its data: `renderGraph`, `loadDocuments`
  //: and `loadLibrary` below are all defined in a file that is fetched here.
  const lazy = TAB_MODULES[name];
  if (lazy) await ensureModule(lazy);

  // Relocate the back-to-top button so it aligns with the chat area bounds
  const scrollTopBtn = document.querySelector(".scroll-top");
  if (scrollTopBtn) {
    if (name === "chat") {
      document.querySelector(".chat-dock")?.appendChild(scrollTopBtn);
    } else {
      document.body.appendChild(scrollTopBtn);
    }
  }
  
  if (name === "dashboard") return whenScriptsLoaded().then(() => renderDashboard());
  if (name === "graph") return renderGraph();
  if (name === "documents") return loadDocuments();
  if (name === "library") return loadLibrary();
  if (name === "reminders") {
    refreshReminderDefaults();
    return loadReminders();
  }
  if (name === "chat") return loadChatSuggestions();
  return undefined; // the notes tab is covered by loadEntries above
}

// --- rendering ---------------------------------------------------------------

// --- icon-aware labels -------------------------------------------------------
//
// Most of the app's small controls are built in JS and take a plain string
// label: chip("Notes"), smallButton("Delete", …), { label: "Improve" }. That
// is why the emoji reform kept missing three hundred icons: they are not in
// index.html, they are string literals passed to functions that assign
// textContent, and you cannot put an <i> in a textContent.
//
// So the label grammar gains one form: a leading `ph:name ` marker.
//
//     chip("ph:file-text Notes")   ->   <i class="ph ph-file-text"></i> Notes
//     smallButton("ph:trash", …)   ->   <i class="ph ph-trash"></i>
//
// Everything else about a label is unchanged, and a label with no marker is
// still set with textContent, so nothing here can turn user text into markup.
// The marker is matched with an anchored, bounded pattern and the captured
// name is rebuilt into a class, a caller cannot smuggle a second class or a
// closing tag through it.
//
// Prose never carries a marker. A toast, a tooltip and anything sent to the
// model are sentences, and `ph:link` in the middle of one is just noise the
// reader has to decode.
const PH_LABEL = /^ph:([a-z0-9-]{1,40})\s*/;
//: **And one at the end**, for a label that carries its own action mark: a
//: chip with a "remove" cross on the right is the shape the whole app uses
//: for "this is attached, take it off", and before this the only way to draw
//: it was to put the character U+2715 in the string. That reads as the app's
//: icon set from a distance and is nothing of the kind up close: measured,
//: the glyph came out system-ui 13.6px at weight 500 beside a Phosphor icon
//: at 15.6px and weight 400, in the same chip (INBOX 263: "I want to strip
//: all signs of being vibecoded by an ai from the ui"). One rule in the
//: label grammar is cheaper than a hand-built chip per call site, which is
//: standing order 11's whole point.
const PH_LABEL_TRAILING = /\s*ph:([a-z0-9-]{1,40})$/;

// Fills `el` with a label, turning a leading `ph:` marker into a real icon
// element. Returns the element, so it composes.
function setLabel(el, label) {
  let text = String(label ?? "");
  //: Taken off before the leading marker is read, so `ph:file-text Name ph:x`
  //: is an icon, a name and an icon rather than a name ending in "ph:x".
  //:
  //: **Only when something comes before it.** Both patterns match a label
  //: that is nothing but one marker, and the trailing one reading `"ph:x"`
  //: first turned every icon-only button (`smallButton("ph:x")`) into a
  //: `ph-trail`, a decoration's margin and opacity on a control.
  const tail = PH_LABEL_TRAILING.exec(text);
  if (tail && tail.index > 0) text = text.slice(0, tail.index);
  else if (tail) tail.length = 0;
  const match = PH_LABEL.exec(text);
  //: The trailing icon is appended after whatever the rest of this builds, so
  //: it is the last child in every shape a label can take: text only, icon
  //: and text, or icon only.
  const withTail = (built) => {
    if (tail && tail.length) {
      const mark = document.createElement("i");
      mark.className = `ph ph-${tail[1]} ph-trail`;
      mark.setAttribute("aria-hidden", "true");
      built.append(mark);
    }
    return built;
  };
  if (!match) {
    el.textContent = text;
    return withTail(el);
  }
  //: `ph:spin` is the working ring (`spinnerEl`), not an icon.
  const spin = match[1] === "spin";
  const icon = spin ? spinnerEl() : document.createElement("i");
  if (!spin) {
    icon.className = `ph ph-${match[1]}`;
    icon.setAttribute("aria-hidden", "true");
  }
  const rest = text.slice(match[0].length);
  // **The gap is a margin, not a space, and it has to be.** A plain " " text
  // node between the icon and the label is what this did first, and it worked
  // everywhere except in a flex container, where CSS discards anonymous
  // whitespace-only children outright. Half the labels in this app live in
  // flex rows (chips, buttons, status items), so half of them rendered with
  // the glyph jammed against the first letter and the other half did not,
  // which reads as a random inconsistency rather than a rule.
  //
  // Only when there IS following text: an icon-only button must stay exactly
  // as tight as it was, or every icon button in the app gains trailing space
  // and stops being square.
  if (rest) icon.classList.add("ph-lead");
  el.replaceChildren(icon);
  if (rest) {
    const textSpan = document.createElement("span");
    textSpan.className = "ph-text";
    textSpan.textContent = rest;
    el.append(textSpan);
  }
  return withTail(el);
}

//: **Is the Settings dialog open?** Defined here, in app.js, and not in
//: settings.js where the rest of that dialog lives. Reported from a real
//: session, five times in one second:
//:
//:     Uncaught ReferenceError: settingsModalOpen is not defined
//:       at HTMLDocument.<anonymous> (app.js:30278)
//:
//: app.js registers its document-wide keydown handler while it parses, and
//: settings.js is the last script on the page -- so every key pressed in the
//: window between the two threw, and the handler that runs Escape, "/" and
//: every other shortcut died with it. One call site already carried a
//: `typeof ... === "function"` guard, which is the same bug being worked
//: around one line at a time. A three-line DOM check has no reason to live in
//: another file; moving it removes the window entirely rather than papering
//: over it at each caller.
function settingsModalOpen() {
  const modal = document.getElementById("settings-modal");
  return Boolean(modal) && !modal.classList.contains("hidden");
}

//: A chip's words are always a `.ph-text` span (DESIGN.md, "A chip"): bare
//: text cannot be trimmed to the x-height band and sits a pixel off its row.
function chipWords(el, text) {
  el.replaceChildren(Object.assign(document.createElement("span"), { className: "ph-text", textContent: text }));
  return el;
}

function chip(text, extraClass = "", onClick = null) {
  const span = document.createElement("span");
  span.className = `chip ${extraClass}`.trim();
  setLabel(span, text);
  if (text && !span.firstElementChild) chipWords(span, text);
  // An interactive chip must be reachable and operable by keyboard, not just
  // the mouse. Passing onClick makes it a real button in the a11y tree.
  if (onClick) {
    span.classList.add("chip-interactive");
    span.setAttribute("role", "button");
    span.setAttribute("tabindex", "0");
    span.addEventListener("click", onClick);
    span.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onClick(event);
      }
    });
  }
  return span;
}

//: One filled button per dialog (DESIGN.md, "Buttons: the ramp"): a
//: stage-gated pair hands the fill from `a` to `b` when b's turn comes.
function stagePrimary(a, b, bTurn) {
  $(a)?.classList.toggle("ghost", !!bTurn);
  $(b)?.classList.toggle("ghost", !bTurn);
}

//: The one "working" ring (DESIGN.md, "Something is working on it"): in a
//: label write `ph:spin Working…`. All of it is the `.spinner` class.
function spinnerEl() {
  const el = document.createElement("span");
  el.className = "spinner";
  el.setAttribute("aria-hidden", "true");
  return el;
}

//: A busy button: disabled, `aria-busy`, the ring first. `label` swaps the
//: words meanwhile; off puts back exactly what was there. Idempotent.
function setBusy(button, busy, label = null) {
  if (!button) return;
  if (busy) {
    if (!button._busyWas) {
      button._busyWas = { kids: [...button.childNodes], disabled: button.disabled };
    }
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    if (label !== null) {
      setLabel(button, `ph:spin ${label}`);
    } else if (!button.querySelector(":scope > .spinner")) {
      const ring = spinnerEl();
      ring.classList.add("ph-lead");
      button.prepend(ring);
    }
    return;
  }
  const was = button._busyWas;
  button.removeAttribute("aria-busy");
  if (!was) return;
  button._busyWas = null;
  button.replaceChildren(...was.kids);
  button.disabled = was.disabled;
}

// --- asking before something irreversible (§35F) ----------------------------------
//
// `window.confirm` is not dependable in pywebview: a backend without it
// returns `undefined`, which `if (!confirm(...)) return;` reads as "no", so
// the button silently did nothing ("the recycle bin empty now button doesn't
// work either"). This dialog is styled like the app and can mark danger.
//: `checkbox` (`{label, title, checked}`) adds one optional second decision
//: ("also take this picture out of the notes that show it") and resolves to
//: `{ok, checked}`; without it callers still get a plain boolean.
//: **The button says what it does**, never "OK" where a verb fits: with no
//: label, the question's first word is used when it is one of these actions.
const CONFIRM_VERBS = new Set([
  "delete", "remove", "clear", "discard", "reset", "replace", "archive", "leave",
  "disconnect", "overwrite", "restore", "empty", "forget", "unlink", "stop",
  "merge", "move", "rename", "revert", "undo", "lock",
]);
function confirmVerb(message) {
  const first = String(message || "").trim().split(/\s+/)[0]?.replace(/[^A-Za-z]/g, "") || "";
  return CONFIRM_VERBS.has(first.toLowerCase())
    ? first[0].toUpperCase() + first.slice(1).toLowerCase()
    : "OK";
}

function confirmDialog(message, options = {}) {
  const {
    confirmLabel = confirmVerb(message),
    cancelLabel = "Cancel",
    danger = true,
    checkbox = null,
  } = options;
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");

    const card = document.createElement("div");
    card.className = "card modal-card confirm-card";
    const text = document.createElement("p");
    text.className = "confirm-text";
    // Blank lines in these messages are deliberate paragraphs, the second is
    // usually the consequence ("This cannot be undone"), which is the part
    // worth reading, so it is not run together with the first.
    //: With more than one paragraph the first is the question ("Quit
    //: Tessellate?", "Delete this note?") and is set as the dialog's title,
    //: the consequence under it in the body voice, the shape every native
    //: confirm has. One paragraph stays one paragraph.
    const parts = String(message).split(/\n{2,}/);
    parts.forEach((part, index) => {
      const line = document.createElement(index === 0 && parts.length > 1 ? "strong" : "span");
      if (index === 0 && parts.length > 1) line.className = "confirm-title";
      line.textContent = part;
      text.append(line, document.createElement("br"));
    });
    const row = document.createElement("div");
    row.className = "row confirm-actions";

    //: Built before `close`, which reads it.
    let extra = null;
    if (checkbox) {
      const label = document.createElement("label");
      label.className = "checkbox-label confirm-extra";
      extra = document.createElement("input");
      extra.type = "checkbox";
      extra.checked = Boolean(checkbox.checked);
      const caption = document.createElement("span");
      caption.textContent = checkbox.label;
      label.append(extra, caption);
      if (checkbox.title) label.title = checkbox.title;
      card.appendChild(label);
    }

    let settled = false;
    const close = (answer) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      returnFocus?.focus?.();
      resolve(checkbox ? { ok: answer, checked: answer && Boolean(extra?.checked) } : answer);
    };
    const onKey = (event) => {
      // Escape cancels and Enter confirms, but only while this dialog is up, 
      // captured, so a keyboard shortcut elsewhere can't fire underneath it.
      if (event.key === "Escape") {
        event.stopPropagation();
        close(false);
      } else if (event.key === "Enter" && event.target.tagName !== "BUTTON") {
        event.stopPropagation();
        close(true);
      }
    };

    const returnFocus = document.activeElement;
    const cancel = smallButton(cancelLabel, cancelLabel, () => close(false));
    const go = smallButton(confirmLabel, confirmLabel, () => close(true), false);
    if (danger) go.classList.add("danger");
    row.append(cancel, go);
    //: `insertBefore`, because the checkbox above was appended to the card
    //: already and the buttons belong under it.
    card.insertBefore(text, card.firstChild);
    card.appendChild(row);
    overlay.appendChild(card);
    // Clicking the backdrop cancels, the way every other overlay here behaves.
    wireBackdropClose(overlay, () => close(false));
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(overlay);
    // Cancel takes focus, not the dangerous one: a stray Enter or Space
    // arriving with the dialog must not be the thing that deletes the notes.
    cancel.focus();
  });
}

// `confirmDialog`'s missing sibling: ask for a line of text.
//
// DESIGN.md bans `window.confirm` because the desktop shell does not reliably
// implement it, and a button gated behind one that returns `undefined`
// silently does nothing. `window.prompt` is the same trap with the same shell,
// and the app has been calling it for every rename, so this is not a new
// dialog for a new feature, it is the one the rule always implied.
//
// Resolves to the trimmed text, or "" for cancel/empty. "" rather than null so
// every caller's guard is the same shape as the confirm one.
//: `segment`, when given, adds **one** segmented control under the field:
//: `{label, options: [{value, label, title}], value}`. The dialog then
//: resolves `{text, choice}` instead of a bare string.
//:
//: One extra control in the dialog that already exists, rather than a second
//: dialog after this one. CLAUDE.md records why in as many words: bookmark URL
//: editing was reported broken five times while working end-to-end every time,
//: and the fault was never the handler, "a second modal that only appears
//: *after* you commit the first is a bad way to expose a second field". Naming
//: a new board and saying what kind of board it is are one decision.
function promptDialog(message, initial = "", { confirmLabel = "Save", segment = null } = {}) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");

    const card = document.createElement("div");
    card.className = "card modal-card confirm-card prompt-card";
    //: **A title row, not a sentence above a field.** Reported as one of two
    //: dialogs off the modal recipe: this card's first child was a `<p>`, so
    //: the "New board" dialog had no heading at all while every other dialog
    //: in the app leads with one. Every `promptDialog` message is a short
    //: prompt ("Name the new board:", "Rename this chat:", "Tag to add to the
    //: selected notes:"), which is a title, so all twenty-odd callers are
    //: right to promote it rather than only this one.
    //:
    //: `confirmDialog`'s message stays a `<p>`: that one really is a
    //: sentence, often two, and a question is body copy.
    const head = document.createElement("div");
    head.className = "row confirm-head";
    const text = document.createElement("h3");
    text.className = "confirm-title";
    text.textContent = message;
    head.appendChild(text);
    const input = document.createElement("input");
    input.type = "text";
    input.value = initial;
    input.setAttribute("aria-label", message);

    //: The optional segmented control. `.seg`, the app's own recipe: the
    //: same one the Library's Cards/Rows switch and the dashboard's range
    //: pickers use: so this is a control the user has already met.
    let chosen = segment?.value ?? segment?.options?.[0]?.value ?? null;
    let segRow = null;
    let segField = null;
    if (segment?.options?.length) {
      //: **The choice is named, and the two options fill their track.**
      //: Reported: "also redesign that whiteboard and mindmap toggle in the
      //: popup, its ugly", with a screenshot of the New board dialog. Two
      //: things were wrong in it and both are about the track. `.seg` is
      //: `display: inline-flex`, which in this card (a flex column that
      //: stretches its children) makes the *track* full width while the two
      //: buttons keep their content width: the right half of the pill was
      //: empty, so the control read as a stray bar with two words in it. And
      //: nothing on screen said what the choice was for, because
      //: `segment.label` only ever reached `aria-label`, which a sighted
      //: reader cannot see.
      //:
      //: The label is now drawn, the buttons share the track equally (the CSS
      //: in 06-timeline-dialogs.css), and each option can carry an icon
      //: through `setLabel`'s "ph:name Label" contract, so Board and Mind map
      //: are told apart by shape before they are read.
      segField = document.createElement("div");
      segField.className = "confirm-seg-field";
      if (segment.label) {
        const segLabel = document.createElement("span");
        segLabel.className = "confirm-seg-label";
        segLabel.textContent = segment.label;
        segField.appendChild(segLabel);
      }
      segRow = document.createElement("div");
      segRow.className = "seg seg-compact confirm-seg";
      segRow.setAttribute("role", "group");
      segRow.setAttribute("aria-label", segment.label || message);
      segField.appendChild(segRow);
      for (const option of segment.options) {
        const button = document.createElement("button");
        button.type = "button";
        setLabel(button, option.label);
        button.dataset.value = option.value;
        if (option.title) button.title = option.title;
        button.classList.toggle("active", option.value === chosen);
        button.setAttribute("aria-pressed", option.value === chosen ? "true" : "false");
        button.addEventListener("click", () => {
          chosen = option.value;
          for (const sibling of segRow.querySelectorAll("button")) {
            const on = sibling.dataset.value === chosen;
            sibling.classList.toggle("active", on);
            sibling.setAttribute("aria-pressed", on ? "true" : "false");
          }
          // Straight back to the name: choosing the kind is a detour on the
          // way to typing, not the end of the interaction.
          input.focus();
        });
        segRow.appendChild(button);
      }
    }

    let settled = false;
    const close = (answer) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      returnFocus?.focus?.();
      // The shape changes only when a segment was asked for, so every existing
      // caller keeps the bare string it has always awaited.
      resolve(segment ? { text: answer, choice: chosen } : answer);
    };
    const onKey = (event) => {
      // Captured, so a shortcut elsewhere cannot fire underneath the dialog, 
      // the same reason confirmDialog captures.
      //
      // **preventDefault, not just stopPropagation.** Reported: pressing
      // Enter after typing a title looked like it "did nothing" - the title
      // was in fact saved (a real POST fired), but the dialog immediately
      // reopened empty, so the user only ever saw a blank prompt sitting
      // there. `close()` below returns focus to whatever triggered the
      // dialog - here, the "+ New document" button - synchronously, *while
      // this Enter keypress is still in flight*. Stopping propagation keeps
      // the keydown from reaching the input as a target, but the browser
      // still owes this physical key its native activation behaviour, and
      // now that behaviour lands on the button that just regained focus:
      // its own "Enter activates the focused button" default action fires,
      // clicking it again and opening a second, blank dialog. preventDefault
      // is what tells the browser this key press is spoken for.
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        close("");
      } else if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        close(input.value.trim());
      }
    };

    const returnFocus = document.activeElement;
    const row = document.createElement("div");
    row.className = "row confirm-actions";
    row.append(
      smallButton("Cancel", "Cancel", () => close("")),
      smallButton(confirmLabel, confirmLabel, () => close(input.value.trim()), false)
    );
    card.append(head, input);
    if (segField) card.append(segField);
    card.append(row);
    overlay.appendChild(card);
    wireBackdropClose(overlay, () => close(""));
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(overlay);
    // The text, selected: a rename usually replaces the name rather than
    // editing it, and a caret at position 0 makes you clear it by hand first.
    input.focus();
    input.select();
  });
}

//: Shared by every overlay's backdrop-click-to-close.
//:
//: Reported directly: "when I try to highlight text in text boxes in popup
//: displays, the popup often just closes." `click` fires wherever the mouse
//: went *up*, not where it went down, so starting a text selection inside
//: the card and releasing outside it (a completely normal way to select the
//: last word or two) fires a click whose target is the backdrop, which every
//: one of these listeners used to read as "the backdrop was clicked" and
//: close on. Recording where the *mousedown* started tells the two apart: a
//: real backdrop click starts and ends on the backdrop; a selection drag
//: starts inside the card.
//: `alsoBackdrop` is a selector for elements that *look* like empty space
//: even though they are not the overlay itself, a full-width layout column
//: whose own box extends well past the thing it is centring.
//:
//: Reported: "I cant click off the documents or images to close the lightbox
//: and the close button doesnt work all the time." Measured with the viewer
//: open on a 1440x900 window: `.lightbox-column` is **1396px wide and 134px
//: tall**, so the whole horizontal band either side of the picture belongs to
//: the column, not the backdrop. The four screen edges did close it, which is
//: why this reads as intermittent rather than broken: whether a click "off
//: the image" works depends on whether it landed above or beside it.
//:
//: The elements named by the caller are the ones with no content of their
//: own. `e.target === el` still has to hold for each: a click that lands on
//: the picture, the caption, a button or any other real child is a click on
//: that child, and closes nothing.
function wireBackdropClose(overlay, close, alsoBackdrop = "") {
  const isBackdrop = (target) =>
    target === overlay || (alsoBackdrop && target instanceof Element && target.matches(alsoBackdrop));
  let downOnBackdrop = false;
  overlay.addEventListener("mousedown", (e) => {
    downOnBackdrop = isBackdrop(e.target);
  });
  overlay.addEventListener("click", (e) => {
    if (isBackdrop(e.target) && downOnBackdrop) close();
  });
}

function smallButton(label, title, onClick, ghost = true) {
  const button = document.createElement("button");
  button.className = ghost ? "ghost small" : "small";
  setLabel(button, label);
  // **A button whose whole content is one glyph is square, without the caller
  // remembering `.icon-only`.** Reported: "the backup x buttons arent square":
  // `smallButton("x", ...)` kept `button.small`'s text padding. CSS cannot see
  // text, so this decides it: setLabel emits `.ph-text` only when a label
  // followed the icon, and a bare character label leaves one character behind.
  if (!button.querySelector(".ph-text") && button.textContent.trim().length <= 1) {
    button.classList.add("icon-only");
  }
  button.title = title;
  //: The title names a glyph only; words name themselves (WCAG 2.5.3).
  if (title && button.classList.contains("icon-only")) button.setAttribute("aria-label", title);
  button.addEventListener("click", onClick);
  return button;
}

//: **A tab's code arrives when the tab does** (WORLD_CLASS_PLAN A1). Measured
//: on this head before the change: 13 blocking scripts and 1,699 KB of
//: compressed JS parsed before the first tab could draw, of which whiteboard
//: (678 KB), documents (640 KB), library (404 KB) and the two graph files
//: (334 KB) are surfaces most sessions never open. `ensureP5` above is the
//: same idea for the one decoration that was bigger than all of them.
//:
//: Two bundles, not five, because the five files are not five independent
//: modules: library.js renders the boards gallery from whiteboard.js and the
//: documents list from documents.js, whiteboard.js calls back into both, and
//: documents.js renders the library's own filters. That cycle is real (it is
//: one surface split across three files, not three surfaces), so splitting it
//: further would only mean loading two thirds of it and waiting for the rest.
//: The graph pair has no edge into it at all once `formatFileSize` moved to
//: this file, so it stands alone.
//:
//: `async = false` on a dynamically inserted script is what keeps them in
//: document order: a dynamic script defaults to async, and library.js running
//: before documents.js would be a different program.
const LAZY_MODULES = {
  //: d3 (90 KB gzipped) comes with the two surfaces that use it, not at boot
  //: (audit FE-07); `ensureModule` fetches a file once whichever bundle names
  //: it first.
  graph: ["/vendor/d3.v7.min.js", "/css/graph-lazy.css", "/js/graph.js", "/js/graph-canvas.js"],
  //: The image viewer (2026-09-27, the boot-script gzip budget): see
  //: lightbox-view.js's header.
  lightbox: ["/css/lightbox-lazy.css", "/js/lightbox-view.js"],
  activity: ["/js/activity-panel.js"],
  //: Run, preview and test for a code document (DOCUMENTS_PLAN 23, D1): the
  //: protocol and its languages, loaded on the first Run.
  run: ["/js/run-core.js", "/js/run-tests.js", "/js/run-debug.js"],
  editConflict: ["/js/edit-conflict.js"],
  categories: ["/js/categories-panel.js"],
  //: The tag manager and the bulk tag dialog (INBOX 447): see tag-manager.js.
  tagManager: ["/js/tag-manager.js"],
  //: The menus a note card's category and tag chips open: see chip-menus.js.
  chipMenus: ["/js/chip-menus.js"],
  noteHistory: ["/js/note-history.js"],
  askHistory: ["/js/ask-history.js", "/js/ask-chart.js"],
  //: The Ask box's Use AI switch (ask-compose.js), preloaded below.
  askCompose: ["/css/ask-compose-lazy.css", "/js/ask-compose.js"],
  //: Notes, Questions (questions-view.js), behind two stand-ins.
  questionsView: ["/css/questions-lazy.css", "/js/questions-view.js"],
  settingsData: ["/js/settings-data.js"],
  settingsUi: ["/js/meaning.js", "/js/settings-find.js", "/js/settings-models.js"],
  tagSuggest: ["/js/tag-suggest.js"],
  searchSuggest: ["/js/search-suggest.js"],
  //: The writing desk's model passes (compose, title, save as note); see writing-desk.js.
  writingDesk: ["/js/writing-desk.js"],
  //: An attachment card's click (INBOX 440 (2)): attachment-actions.js.
  attachments: ["/js/attachment-actions.js"],
  //: Tesseract's status line (INBOX 443 (3)): see ocr-engine.js.
  ocrEngine: ["/js/ocr-engine.js"],
  //: Quick note and the note outbox (INBOX 434): see quick-note.js.
  quickNote: ["/js/quick-note.js"],
  fieldClear: ["/js/field-clear.js"],
  //: A date or time field's panel (Phase 12): see date-field.js.
  dateField: ["/js/date-field.js"],
  //: The app emblem as an assistant head (INBOX 463 (2)): assistant-avatar.js.
  assistantAvatar: ["/js/assistant-avatar.js"],
  //: Arranging the dashboard's Quick access row (INBOX 461): quick-access.js.
  quickAccess: ["/css/quick-access-lazy.css", "/js/quick-access.js"],
  notesRail: ["/js/notes-rail-spy.js"],
  //: The dashboard's Boards & maps widget (INBOX 553(d)): see dash-boards.js.
  dashBoards: ["/js/dash-boards.js"],
  //: The suggestions inbox (GRAPH_PLAN KG9): see suggestions-inbox.js.
  inbox: ["/css/inbox-lazy.css", "/js/suggestions-inbox.js", "/js/entity-page.js", "/js/link-types.js", "/js/note-properties.js"],
  //: 2026-10-05 (gzip budget), the next seven: each file's header says why.
  reveal: ["/css/reveal-lazy.css", "/js/reveal-targets.js"],
  onboarding: ["/js/onboarding.js"],
  tour: ["/js/tour.js"],
  updates: ["/js/update-dialogs.js"],
  //: With the feature rows it lists (app-features.js).
  appPalette: ["/js/meaning.js", "/js/app-features.js", "/js/app-palette.js"],
  notePanels: ["/js/note-panels.js", "/js/note-edit-panels.js", "/js/note-pick-preview.js"],
  //: Every listener inside the Settings window, awaited on first open: settings-controls.js.
  settingsControls: ["/css/settings-controls-lazy.css", "/js/settings-controls.js"],
  attachTo: ["/js/pick-row.js", "/js/attach-to.js"],
  vault: ["/js/vault-unlock.js"],
  //: The one icon and emoji picker, on first use (MINDMAP_PLAN decision 43): see icon-picker.js.
  iconPicker: ["/css/icon-picker.css", "/js/icon-picker.js"],
  //: Settings groups, each file's header says which (WORLD_CLASS_PLAN rows 21 to 27).
  modelBench: ["/js/model-bench.js"],
  webClip: ["/js/web-clip.js"],
  appImport: ["/js/app-import.js"],
  usageLedger: ["/css/usage-lazy.css", "/js/usage-ledger.js"],
  //: The Library list without the editors (audit FE-03(c)): they were about
  //: 900 KB gzipped. A document or a board brings the whole `library` surface.
  libraryList: ["/css/library-lazy.css", "/js/library.js"],
  //: The Capture box's template picker (note-templates.js's header).
  noteTemplates: ["/js/note-templates.js"],
  meetings: ["/css/meetings-lazy.css", "/js/meetings.js"],
  quickAdd: ["/css/quickadd-lazy.css", "/js/quickadd.js"],
  //: The Statistics page and This week (statistics.js's header).
  statistics: ["/css/utilities-lazy.css", "/js/ask-chart.js", "/js/statistics.js"],
  utilities: ["/js/utility-tools.js"],
  //: Live captions (captions.js's header; Brief 82).
  captions: ["/css/captions-lazy.css", "/js/captions.js"],
  //: Translate this, the offline translator's sheet (translate.js's header).
  translate: ["/css/utilities-lazy.css", "/js/translate.js"],
  //: The search box, Find anything, and its saved searches (search.js's header).
  search: ["/css/search-lazy.css", "/js/search.js"],
  //: Atlas's blink and arm rig (atlas-motion.js's header): the drawing is
  //: boot's, the motion arrives with the first figure that mounts.
  atlasMotion: ["/js/atlas-motion.js"],
  //: Atlas the Guide as a chat (help-chat.js's header), on first ask.
  helpChat: ["/css/help-chat-lazy.css", "/js/help-chat.js"],
  //: Atlas's mood cues and bold small-size brows (atlas.js `atlasSheet`).
  atlasFaces: ["/css/atlas-lazy.css"],
  //: A selection's Move to space (batch-space.js's header).
  batchSpace: ["/js/batch-space.js"],
  undoKit: ["/js/undo-kit.js"],
  //: Settings, Tasks (chat-tasks.js's header).
  sharedIntake: ["/js/shared-intake.js"],
  //: Settings, Packages: the extras, their bundles and bulk actions (INBOX 595).
  packages: ["/js/settings-packages.js"],
  //: Settings, Search and index's embedding models (INBOX 700, embed-choices.js).
  embedChoices: ["/js/embed-choices.js"],
  //: The panel the "m" chord opens: chord-guide.js says why it is preloaded.
  chordGuide: ["/js/chord-guide.js"],
  //: Atlas's living tail and its rings' loops (the gzip budget): see atlas-life.js.
  atlasLife: ["/js/atlas-life.js"],
  //: The companion's menu and a face's enlarged view (companion-menu.js's header).
  companionMenu: ["/js/companion-menu.js"],
  //: A held drag-selection scrolling a list at its edge (drag-edge.js), preloaded below.
  dragEdge: ["/js/drag-edge.js"],
  //: The back/forward list's rows (INBOX 654): see nav-history.js.
  navHistory: ["/css/nav-history-lazy.css", "/js/nav-history.js"],
  //: "Forgot your password?" and the recovery key (INBOX 663): account-recovery.js.
  accountRecovery: ["/css/recovery-lazy.css", "/js/account-recovery.js"],
  //: The bell's panel and what a row's action does (notifications.js's header).
  notifications: ["/js/notifications.js"],
  //: Tidy, the reviews with no AI (INBOX 691): tidy.js's header.
  tidy: ["/css/tidy-lazy.css", "/js/tidy.js"],
  semanticNotice: ["/js/semantic-notice.js"],
  //: The order the `<script>` tags had, kept: every cross-file call between
  //: these three is inside a function rather than at parse time, so it is not
  //: load-bearing, but it is the order the three files' own headers describe.
  //: documents-code.js and documents-prose.js were split out of documents.js
  //: (2026-09-24) and go *before* it, and that position is load-bearing: their
  //: own top level reads nothing from documents.js, while documents.js's
  //: top-level wiring names their functions, and each file here is followed
  //: by a microtask checkpoint before the next one runs. See their headers.
  //: whiteboard-map.js (the mind map layer, split out of whiteboard.js the
  //: same day) goes before whiteboard.js on the same terms.
  library: [
    //: d3 before whiteboard.js, whose top level calls `d3.zoom()`.
    "/vendor/d3.v7.min.js",
    //: The styles only this bundle's surfaces draw, out of the boot budget.
    "/css/library-lazy.css",
    //: First: the stored undo histories both editors read (undo-store.js).
    "/js/undo-store.js",
    //: The Attach picker's row, drawn synchronously by the board pickers.
    "/js/pick-row.js",
    "/js/documents-code.js",
    "/js/documents-prose.js",
    "/js/documents.js",
    "/js/margin-reader.js",
    "/js/whiteboard-map.js",
    "/js/whiteboard.js",
    "/js/whiteboard-commands.js",
    "/js/whiteboard-library.js",
    //: The New board dialog and every template's picture (INBOX 715).
    "/js/whiteboard-templates.js",
    "/js/whiteboard-format.js",
    "/js/whiteboard-interchange.js",
    "/js/whiteboard-history.js",
    "/js/library.js",
  ],
};

//: Which bundle a tab needs before its own dispatch runs. `documents` is the
//: document editor the Library opens, which is why it shares the Library's
//: bundle rather than having one of its own.
//: INBOX 519: a boot fetch can answer between two scripts, before dashboard.js.
function whenScriptsLoaded() {
  if (document.readyState !== "loading") return Promise.resolve();
  return new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve, { once: true }));
}

const TAB_MODULES = { graph: "graph", library: "libraryList", documents: "library" };

const lazyModuleLoads = new Map();

//: **The stamp is read off the page, never rebuilt from `__version__`.** Every
//: local URL carries `?v=<version>`, and `RevalidatedStatic`
//: (src/tessellate/api/app.py) rewrites it in index.html's served body to
//: `?v=<version>-<hash of that file>`, so an edited file is a new URL and an
//: unchanged one keeps its cache across launches (audit 2026-10-05, FE-02).
//: A script inserted later (a lazy bundle, a worker) takes its own file's
//: stamp from the map the page carries (`<meta name="asset-stamps">`);
//: a hard-coded `?v=0.3.0` here would be a second, staler cache key for the
//: same file, which is the exact bug those stamps exist to prevent.
let assetStampMap = null;
function lazyAssetStamp(file) {
  if (assetStampMap === null) {
    assetStampMap = {};
    const listed = document.querySelector('meta[name="asset-stamps"]')?.getAttribute("content") || "";
    for (const pair of listed.split(",")) {
      const at = pair.indexOf("=");
      if (at > 0) assetStampMap[pair.slice(0, at)] = pair.slice(at + 1);
    }
  }
  const own = file && assetStampMap[file];
  if (own) return `?v=${own}`;
  //: Not in the map (a file the server did not list, or a page served
  //: without the map): app.js's stamp, the closest thing the page has.
  const src = document.querySelector('script[src*="/js/app.js?"]')?.getAttribute("src") || "";
  const query = src.indexOf("?");
  return query === -1 ? "" : src.slice(query);
}

//: **A lazy bundle's "when the page is ready" is now.** Three of the files
//: `ensureModule` inserts wrapped their top-level wiring in a
//: `DOMContentLoaded` listener, which was right when they were `<script>`
//: tags in the head and wrong the moment they loaded on first use: the
//: event had fired minutes earlier, the listener never ran, and every
//: Library sub-tab was a button with no handler ("I cant click on any of
//: the library subtabs"). This runs the wiring at once when the document is
//: already parsed and defers it only while it is still loading, so a file
//: behaves the same whether it arrived at boot or on demand.
//: A microtask, not a direct call: the wiring sits in the middle of its file
//: and reads `let` bindings declared further down (`libraryMediaKind`), which
//: a direct call reached before they existed ("Cannot access before
//: initialization"). A microtask runs once the whole script has evaluated,
//: which is the same moment `DOMContentLoaded` gave a boot-time script.
function onDomReady(fn) {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
  else queueMicrotask(fn);
}

//: One fetch per file, whichever bundle asks first: d3 is in two. An
//: `async = false` script runs in insertion order with every other one, so a
//: bundle reusing a file still in flight still runs after it.
const lazyFileLoads = new Map();
function lazyScript(file) {
  if (!lazyFileLoads.has(file)) {
    lazyFileLoads.set(
      file,
      new Promise((resolve) => {
        //: A bundle's own stylesheet is a `<link>` (library-lazy.css's header).
        const css = file.endsWith(".css");
        const el = document.createElement(css ? "link" : "script");
        if (css) el.rel = "stylesheet";
        else el.async = false; // document order, not network order
        el[css ? "href" : "src"] = file + lazyAssetStamp(file);
        el.onload = () => resolve(true);
        el.onerror = () => resolve(false);
        document.head.appendChild(el);
      })
    );
  }
  return lazyFileLoads.get(file);
}

function ensureModule(name) {
  const files = LAZY_MODULES[name];
  if (!files) return Promise.resolve(false);
  if (!lazyModuleLoads.has(name)) {
    lazyModuleLoads.set(name, Promise.all(files.map(lazyScript)).then((results) => results.every(Boolean)));
  }
  return lazyModuleLoads.get(name);
}

//: **The note editor's door, kept at boot.** The rendering editor every note
//: box gets (documents.js's `NOTE_SURFACES` table and `mountNoteSurface`)
//: mounts on the box's first focus through a listener *in documents.js*,
//: which is in the Library bundle now. So on a fresh boot the capture box,
//: the edit form, the draft and the graph's popup all stayed bare textareas
//: until the Library tab had been visited once (the owner: "the graph popup
//: panels no longer auto render the md and images"). This listener is the
//: half that has to live in the file that is always loaded: it fetches the
//: bundle on the first focus of a note box and hands the mount over. Once
//: the bundle is in, its own listener runs on every later focus and this
//: one steps aside. `NOTE_SURFACE_IDS` mirrors the table's keys, and
//: `tests/test_note_surface.py` fails when the two drift.
const NOTE_SURFACE_IDS = new Set([
  "entry-content",
  "entry-edit-content",
  "graph-popup-content",
  "graph-new-content",
  "draft-text",
  "draft-thoughts",
  "wb-card-editor",
]);

//: Mount the editor on one note box now, fetching the bundle if it is not in
//: yet. Resolves to the surface (or null when the engine is unavailable) so
//: a caller that sizes itself to the box can re-place afterwards. Used by
//: the graph popup, which opens rendered rather than waiting for a click.
function mountNoteSurfaceNow(host) {
  if (!host || !NOTE_SURFACE_IDS.has(host.id)) return Promise.resolve(null);
  return ensureModule("library").then((ok) => {
    if (!ok || typeof mountNoteSurface !== "function" || typeof NOTE_SURFACES !== "object") return null;
    return mountNoteSurface(host, NOTE_SURFACES[host.id]);
  });
}

document.addEventListener("focusin", (event) => {
  const host = event.target;
  if (!(host instanceof HTMLTextAreaElement) || !NOTE_SURFACE_IDS.has(host.id)) return;
  //: documents.js is in: its own delegated listener mounts and focuses.
  if (typeof mountNoteSurface === "function") return;
  mountNoteSurfaceNow(host).then((surface) => {
    //: Focus moved on while the bundle was fetching: mount, but do not
    //: steal the caret back.
    if (surface && surface.kind === "codemirror" && document.activeElement === host) surface.focus();
  });
});

//: **Tab indents from the first keystroke** (owner, INBOX 392: "indenting and
//: dedenting across the app also doesnt come in the form it should"). The
//: editor that owns Tab and Shift+Tab (documents.js `indentDocSelection`)
//: arrives with the Library bundle on a note box's first focus, and until it
//: has, the box is a plain textarea: measured on a fresh boot, "- alpha"
//: plus Tab moved focus to the tags field instead of indenting. This bridges
//: that second or two with the same rule the editor applies: whole lines,
//: two spaces, list items as blocks, Shift+Tab only when there is something
//: to take off (so a flush-left caret still tabs backwards out of the box).
//: Once the bundle is in, the textarea is replaced and this never runs.
document.addEventListener("keydown", (event) => {
  const box = event.target;
  if (event.key !== "Tab" || event.ctrlKey || event.altKey || event.metaKey) return;
  if (!(box instanceof HTMLTextAreaElement) || !NOTE_SURFACE_IDS.has(box.id)) return;
  const value = box.value;
  const selStart = box.selectionStart;
  const selEnd = box.selectionEnd;
  const lineStart = value.lastIndexOf("\n", selStart - 1) + 1;
  const endBreak = value.indexOf("\n", selEnd > selStart ? selEnd - 1 : selEnd);
  const lineEnd = endBreak === -1 ? value.length : endBreak;
  const lines = value.slice(lineStart, lineEnd).split("\n");
  let next;
  if (event.shiftKey) {
    const indent = /^( {1,2}|\t)/;
    if (!lines.some((line) => indent.test(line))) return;
    next = lines.map((line) => line.replace(indent, ""));
  } else {
    next = lines.map((line) => `  ${line}`);
  }
  event.preventDefault();
  const text = next.join("\n");
  box.setRangeText(text, lineStart, lineEnd, "preserve");
  const shift = next[0].length - lines[0].length;
  box.selectionStart = Math.max(lineStart, selStart + shift);
  box.selectionEnd = selEnd + (text.length - (lineEnd - lineStart));
  box.dispatchEvent(new Event("input", { bubbles: true }));
});

//: **The entry points that can be reached before their own file exists.**
//:
//: Most calls into a lazy module happen on its own tab, after `switchTab` has
//: awaited it. These are the ones that do not: a map chip in the note list
//: opens a board, the command palette opens a document, the notes editor's
//: bold button is documents.js's `applyMarkdown`, and eight of graph.js's
//: functions are read as *bare identifiers* by this file's own top-level
//: wiring (the click listener this file binds on `#graph-popup-close` names
//: `closeGraphPopup` as a bare identifier), which is evaluated the moment that
//: line runs and would throw ReferenceError with graph.js absent.
//:
//: Each name below gets a stand-in that loads the bundle and then calls the
//: real function, which has replaced the stand-in by then: a top-level
//: `function foo()` in a classic script rebinds `globalThis.foo`, so no
//: hand-off is needed beyond looking the name up again.
//:
//: Two rules decide what is on this list, and both matter:
//:
//: 1. **Only functions whose return value nobody reads.** A stand-in has to
//:    return a promise, so a function whose answer is used in the same
//:    statement cannot have one. `docEventFromCm` is the sharp case: editor.js
//:    reads it as `if (typeof docEventFromCm === "function" &&
//:    docEventFromCm(event.target)) return;`, and a promise is truthy, so a
//:    stand-in there would swallow every keystroke in the note editor. Those
//:    functions are left off, and their `typeof` guard then means what it
//:    says: the document surface is not loaded, so this is not one.
//: 2. **Only functions a person's own gesture reaches.** `loadLibrary` and
//:    `renderLibrary` are deliberately absent: they are called from "refresh
//:    the list if it is on screen" guards after an OCR pass or an import
//:    finishes, and a stand-in would pull 1.7 MB in the background because a
//:    caption came back. Skipping is the right answer when the Library has
//:    never been opened; opening it loads and renders it anyway.
const LAZY_ENTRY_POINTS = {
  //: The palette's Live captions row (captions.js; Brief 82): nobody reads its return.
  captions: ["toggleLiveCaptions"],
  lightbox: ["openLightbox"],
  editConflict: ["editConflictPrompt"],
  noteHistory: ["openEntryHistory", "undoSkillRun"],
  modelBench: ["renderModelBench"],
  usageLedger: ["renderUsage", "renderCaptureCommand"],
  packages: ["renderExtras"],
  embedChoices: ["renderEmbedChoices"],
  chordGuide: ["showTabJumpHint"],
  //: The icon and emoji picker: reached through `pickIconOrEmoji` (editor.js).
  iconPicker: ["openIconPicker"],
  //: Async, and reached from a Settings pane drawn before the window's own await.
  settingsControls: ["refreshSearxngHost", "renderStatusBarSettings", "renderMcpSnippet", "renderLanAccess", "renderMemorySettings"],
  settingsData: [
    "renderPrivacyRange",
    "renderPrivacyReceipt",
    "renderBackups",
    "renderBackupRetention",
    "backupNow",
    "importDirectory",
    "importMarkdown",
    "importDocument",
  ],
  tagSuggest: ["openTagSuggest", "renderReevaluateResult"],
  writingDesk: ["composeDraft", "suggestDraftTitle", "saveDraftAsNote", "draftSaveMenuInit"],
  //: Each called for its effect when a figure mounts or moves; nothing reads a result.
  atlasMotion: ["atlasBlinkStart", "atlasRigAttach", "atlasRigWake"],
  companionMenu: ["nameMarkBuddyMenu", "openNameMarkViewer", "mountBuddyPresets"],
  //: Opened, asked or drawn for their effect; `openHelpChat`'s close is read by no caller.
  helpChat: ["openHelpChat", "askAtlas", "renderAtlasStarters"],
  batchSpace: ["batchMoveToSpace"],
  notifications: ["openNotifications"],
  sharedIntake: ["takeSharedIntake"],
  undoKit: ["pushEntryCreateUndo", "pushLinkCreateUndo", "pushRequestUndo", "pushEntriesPutUndo", "pushBinPairUndo", "pushRoutePairUndo", "pushTensionLinkUndo", "pushTokenUndo", "pushUploadUndo", "pushCorrectionUndo", "pushMadeUndo", "pushTextUndo", "pushWikiRenameUndo"],
  tidy: ["openTidySheet"],
  semanticNotice: ["semanticInstallNotice", "semanticOnboardingOffer"],
  questionsView: ["initQuestionsView", "loadQuestions"],
  //: 2026-10-05, the next six: async or unread, reached by a gesture.
  reveal: ["revealFeature"],
  onboarding: ["openOnboarding", "maybeShowConsoleViewIntro"],
  tour: ["openTour", "renderTourReplay"],
  updates: ["checkForUpdate", "applyUpdateNow", "showSourceUpdatedDialog", "askUpdateChoiceOnce"],
  appPalette: ["openPalette"],
  notePanels: ["beginOrCompleteLink", "toggleRelated", "toggleReferences", "toggleFaded", "toggleNoteReminders", "renderRelatedWhileEditing", "renderNoteBookmarksWhileEditing", "renderEditForm", "richPickerNote"],
  vault: ["unlockPrivateNotes", "ensureVaultOpen"],
  accountRecovery: ["openForgotPassword", "offerRecoveryKey", "showRecoveryKey", "makeRecoveryKey", "recoveryAccountRow"],
  attachTo: ["renderAttachToBoard", "renderAttachToDocument", "renderNotePickerList"],
  noteTemplates: ["openNoteTemplateDialog", "useNoteTemplate", "templateCatalogue"],
  quickAdd: ["quickAddAttach", "quickAddSlots", "quickAddAsk", "quickAddClear", "magicAddReminder"],
  //: Opened by a gesture; the closers are called only once it is open.
  search: ["openFinder"],
  statistics: ["openStatistics", "renderWeekWidget"],
  meetings: ["openNewMeeting", "openMeetingSheet", "openMeetingRecorder"],
  askHistory: [
    "toggleAskHistoryPanel",
    "loadAskHistoryPage",
    "clearAskHistory",
    "viewAskHistoryTurn",
    "toggleAskHistoryPin",
    "deleteAskHistoryTurn",
  ],
  categories: [
    "openManageCategories",
    "mergeCategoryFromPanel",
    "splitCategoryFromPanel",
    "deleteCategoryFromPanel",
    "renameCategory",
    "deleteCategory",
    "restoreCategoryMoves",
    "chooseNoteCategory",
    "showCategoryNotes",
    "moveNotesToCategory",
    "pickCategoryColour",
  ],
  tagManager: ["openTagsSheet", "openBulkTags", "renameTagEverywhere", "removeTagFromNote"],
  chipMenus: ["openCategoryChipMenu", "openTagChipMenu"],
  attachments: ["attachmentAction"],
  ocrEngine: ["ocrEngineMount"],
  quickAccess: ["quickAccessEdit"],
  inbox: ["openSuggestionsInbox", "openEntityPage", "openEntitiesSheet", "openLinkTypeSheet", "openRelationTypesSheet", "openNotePropertiesSheet", "openNoteTypesSheet", "openQueryTable", "showQueryOnGraph"],
  assistantAvatar: ["assistantEmblemInto"],
  quickNote: ["openQuickNote", "pasteClipboardAsNote", "saveChatAnswerAsNote", "reminderFromChatAnswer", "createNoteSafely", "noteOutboxAdd", "flushNoteOutbox", "renderPendingNoteRows"],
  graph: [
    "clearTrace",
    "closeGraphNewNote",
    "openGraphControlsSheet",
    "closeGraphPopup",
    "exportGraphPng",
    "openGraphNewNote",
    "placeGraphPopup",
    "renderGraph",
    "saveGraphNewNote",
    "saveGraphPopup",
    //: The layout picker's change handler (navigation.js) calls it: on the
    //: Graph tab before the bundle has arrived (a cold first visit, the
    //: picker changed at once) it threw "setGraphPhysicsEnabled is not
    //: defined" and the change was lost (the companion agent's
    //: companionreact.js, 2026-09-26). Nobody reads its return value.
    "setGraphPhysicsEnabled",
    "setTracePanelOpen",
    "syncGraphPopupSave",
  ],
  library: [
    "applyDocGutter",
    "applyMarkdown",
    "archiveDocumentWithUndo",
    "closeDocAiPanel",
    "createConceptMap",
    "createDocument",
    "createNewBoard",
    "expandNoteIntoDocument",
    "initDocSidebarTabs",
    "loadDocuments",
    "markDocDirty",
    "mountDocToolbarControlsFor",
    "mountGutterFor",
    "openDocDictionary",
    "openDocTemplateDialog",
    "openDocument",
    "renderDocStorage",
    "saveDocument",
    "showDocSidebarSection",
    "toggleDocFindBar",
    "wbOpenBoardSearch",
    "wbShowBoardsLanding",
    "wbShowCanvasView",
    "wbToggleNavigator",
    "wireMarkdownToolbar",
    "wireMdFormatShortcuts",
    "openWhiteboardBoard",
    "deleteDocumentWithUndo",
    "offerCreateUndo",
    "offerCreatedDocsUndo",
    "renameDocumentWithUndo",
    "jumpToDocLine",
    "renderLibraryBoardsGallery",
  ],
  //: The Library's own list (audit FE-03(c)): library.js alone. A call from
  //: it into a document or a board is one of `library`'s stand-ins above,
  //: which fetches the editors on first use.
  libraryList: [
    "closeBinnedReader",
    "flashLibraryItem",
    "focusLibraryFile",
  ],
};

function installStandIns(table) {
  for (const [module, names] of Object.entries(table)) {
    for (const name of names) {
      // A name this file (or another that always loads) already defines is that
      // file's, and must not be shadowed.
      if (typeof window[name] === "function") continue;
      const standIn = (...args) =>
        ensureModule(module).then(() => {
          const real = window[name];
          //: The module failed to load (offline, or the file is gone). Calling
          //: the stand-in again here would recurse forever, so this is where it
          //: stops, quietly: the control does nothing, which is what it did
          //: before this list existed.
          if (typeof real !== "function" || real === standIn) return undefined;
          return real(...args);
        });
      window[name] = standIn;
    }
  }
}
installStandIns(LAZY_ENTRY_POINTS);
//: Fetched soon after boot, not on first use: the outbox is for the moment
//: the server is gone, when no script can be fetched (quick-note.js).
setTimeout(() => ["quickNote", "quickAdd", "fieldClear", "chordGuide", "notePanels", "dragEdge", "askCompose", "search"].forEach((name) => ensureModule(name)), 3000);
