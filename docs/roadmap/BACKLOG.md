# Backlog: the numbered sections


> **The other three:** [ROADMAP.md](../ROADMAP.md) (live work) · [BACKLOG.md](BACKLOG.md) (§1–§29) · [ANALYSIS.md](ANALYSIS.md) (§30–§34, including the licence constraint, AGPL-3.0 now) · [HISTORY.md](HISTORY.md) (already built).

Split out of `ROADMAP.md`, which had reached 4,500 lines and 47 sections. This
file is the **standing backlog**: everything that is still work, numbered as it
always was, so every §-reference elsewhere still resolves.

The live list: what to do next, and the two sections of freshly reported work
(§35, §36): stays in [ROADMAP.md](../ROADMAP.md). Analysis and finished work
are in [ANALYSIS.md](ANALYSIS.md) and [HISTORY.md](HISTORY.md).

> **Status, 2026-09-07.** Every UI/UX item in this file (§2 quick wins, §15
> Appearance, §16 Sweeping UI quality-of-life, §19 Accessibility, §24
> Dashboard, §29b's visual rows, §64's editor chrome) is now governed by
> [UI_MODERNISATION_PLAN.md](UI_MODERNISATION_PLAN.md), the top priority in
> ROADMAP.md: do them through its phases, not one by one from here. §6 and
> §63 are done (kept for their numbers). Everything else stands.

> **Swept against the code, 2026-10-05.** Every open item was checked: built ones
> are struck with the file and line that proves it, whiteboard, document, graph and
> harness items point at the plan row that owns them (WHITEBOARD_PLAN, DOCUMENTS_PLAN,
> GRAPH_PLAN, WORLD_CLASS_PLAN, `scratchpad/audit1005/features.md`), and each item
> still open carries a one-line **Next:** naming the files, or says it is the
> owner's call. Line numbers drift; the names beside them do not.

> The rule that governs all of it, unchanged: **check the running app before
> building anything here.** Three sessions independently rebuilt something that
> already existed, and an audit of §2 found four of its six "quick wins" done.

## 1. Live log console (started, not finished)

**Why.** Asked for directly: the Logs screen should read "like the terminal
running in the background, with key errors flagged", not a list you refresh by
hand.

**What exists.** `core/logbuffer.py` is a 500-record ring buffer attached to the
root logger and uvicorn's. It now sanitises each message to one printable line
(so a chat question or a page title can't forge a row) and keeps tracebacks in a
separate `trace` field for a fold.

**What's left.** Streaming (NDJSON over `fetch`, not `EventSource`, see
HISTORY.md for why), follow/tail with autoscroll, level/text/source
filters, the `trace` fold, merging in `browserLogs`, and an error badge on
the nav item are all **done**, see HISTORY.md. Also done: **exporting a
support bundle** (an allowlist zip of the log buffer, scrubbed
`preferences.json`, and model status).

- **Getting one error OUT of the log** (asked for directly after the console
  landed: "make sure that if there is an error in the log that it can be
  accessed and copied"). Each record has its own copy button that takes the
  traceback with it, an open traceback has a **Copy traceback** of its own,
  and "Copy all" relabels to "Copy 12 shown" whenever a filter is hiding
  something. **The real find here was underneath:** every copy in the whole
  app went through `navigator.clipboard`, which browsers expose **only in a
  secure context**. `http://localhost` qualifies, which is why nothing had
  ever shown it: but reach the app at `http://192.168.1.20:8000` or through
  a tunnel (§17's mobile-access question, and the proxied client address §8b
  already saw in a real log) and the API is `undefined`, so every copy button
  in the app was a no-op that said "couldn't copy". Copying now tries the
  modern API, then `execCommand` on plain http, then shows the text
  pre-selected in a dialog. A test asserts no caller writes to
  `navigator.clipboard` directly any more, since a helper only some callers
  use leaves the rest quietly lying.
- ~~**Export a support bundle.**~~ **done**, see below; it is an allowlist,
  not a denylist. One button that zips the log buffer,
  `preferences.json` with anything sensitive stripped, and Ollama/model
  status (`/models/status`) into a file the user attaches to a bug report,
  asked for indirectly ("an interface for managing the application… errors
  etc") and echoed by the outside review's "support bundle" suggestion.
  Everything in it is already local and already visible somewhere in the app;
  this only collects it. No new telemetry: the file is written to disk and
  the user chooses whether to send it, which is the difference between this
  and the outside review's other suggestion (opt-in crash reporting),
  rejected in §30.
- ~~**Confirm nothing is silently dropped.**~~ **Done.** `logbuffer.py`
  tracks `_dropped`/`_dropped_since` (a full ring buffer counts what it
  discards rather than losing the fact silently), and the frontend renders it
  - "N earlier records … the oldest record still kept is from …", whenever
  `stats().dropped` is nonzero.

---

## 2. Quick wins

Small, self-contained, each removing a visible annoyance.

**Nothing here is open, all six are done**, and the section is kept rather
than deleted for two reasons: a `§2` in a code comment still has to land
somewhere, and the *shape* of what happened here is worth keeping. Four of the
six turned out to be **already built when this list was written**, checked in
the running app rather than assumed, because by then three sessions had
independently rebuilt something that already existed. That ratio (four stale
claims out of six) is the single best argument for the "check before you
build" rule at the top of CLAUDE.md, and deleting the evidence would make the
rule look like superstition rather than a measured result.

Already built when claimed as open: the SearXNG install path, the Notes
sidebar sticky rule, a per-code-block copy button in chat answers, and
conversation search by content.

Genuinely built afterwards:

- **Empty chats could not be deleted.** A `Delete` button in the chat toolbar
  now covers both cases, an empty or unsaved pane resets silently, a saved
  one gets the sidebar's own confirm dialog and then
  `DELETE /conversations/{id}`.
- **Document outline / table of contents, word-count goal, reading time**,
  all three, not just the outline. `renderDocOutline` builds the TOC,
  `renderDocStats` shows reading time, and `promptDocWordGoal`
  (`#doc-word-goal`) is a working word-count-goal control. §5 already recorded
  the outline and reading-time halves as done and called the word-count goal
  "the one unbuilt part", it was built too.

---

## 3. Chat page: Chat / Agent / Browse sub-tabs

> **Status (audited this session, ROADMAP.md §38 item 5): substantially done,
> via a different, and, on the evidence, better, shape than "three
> sub-tabs".** Checked against the actual code rather than re-reading this
> section's original wording as a spec:
>
> - **Chat vs Agent** → the Ask/Agent mode toggle in the chat dock, not a
>   tab switch. Same distinction, one click instead of a navigation.
> - **Browse** → the web panel (§36G), a persistent column beside the
>   conversation rather than a third tab, and §36G's own reasoning
>   ("a reading surface cannot live inside a control strip... as a column it
>   needs no cap and sits beside the composer") is a real argument *against*
>   folding it back into a tab, not just a different implementation of the
>   same idea.
> - **Cross-linking** ("the agent hands a page to Browse, Browse hands a page
>   to chat") → `askAboutPage()` does the Browse-to-chat direction (💬 Ask
>   about this closes the panel, asks the agent to `read_url` the page).
> - **Visible plan/progress** → `make_plan`'s ticked-step display, built
>   since (§35's "Next session: start here" item 1), satisfies this more
>   generally than a per-tab progress view would have.
> - **Independent web-search gating** ("works even when the chat/agent
>   web_search tool is off") → there is one `web_search_enabled` pref
>   already, not two competing toggles to decouple; the panel opens
>   regardless and says plainly why a search won't work if it's off, rather
>   than being blocked by a separate "Agent mode" switch.
>
> **The one genuine, real, small gap:** "which tools are allowed this turn,
> max rounds" as a **user-facing** Agent-mode control. `agent.py`'s
> `_agentic_reply` already takes `allowed_tools`/`max_rounds` as real
> parameters, the backend has the knob, but nothing in `app.js` exposes it;
> tool selection is automatic (`tools.focus_for`) with no manual override UI.
> Worth building only if a real use case shows up wanting it (most users want
> automatic selection, not a per-turn allowlist to manage); not worth a
> session on its own.
>
> **Next:** `routes_chat.py:1595` already takes `allowed_tools` on the request and
> `agent.py:1600` takes `max_rounds`; the missing piece is one control in the Agent
> row of `frontend/js/chat-agent.js` (a '?' popover per DESIGN.md) sending them.
> Chat agent area, so it waits for the CHAT_PLAN agent.
>
> ~~**A second small gap, scoped but not built:**~~ **Built, see `frontend/js/chat-agent.js:1548` (`toolChip` is a `<details>` carrying the arguments and the result summary, saved with the turn) and `frontend/css/00-tokens-shell.css:3264`.** The text below is the original scoping. A tool-call chip was a
> flat one-line label (`toolChip()`, app.js ~6200): no way to see what the
> AI actually sent the tool or what came back, purely a cosmetic upgrade
> asked for directly ("a dropdown which shows the input tool call command
> and the output... collapsed by default... doesn't affect the AI, only a
> visual upgrade"). Real but genuinely multi-file, not a CSS tweak: `agent.py`
> already has `arguments` in scope where it builds each tool event but the
> SSE stream to the frontend only ever sends a human-readable `label`, not
> the raw arguments or the raw result, those would need adding to the event
> payload (additively; the model's own context is built from a separate
> prompt-construction path and would be untouched, so this is safe to add
> without the caveat in the ask being a real risk). Frontend: `toolChip()`
> becomes a `<details>`/`<summary>` with two collapsed sections (input as
> formatted JSON, output in a `overflow-y: auto` box for a long result),
> and the chat-history `serialise()`/`replay()` round-trip (app.js ~6083)
> needs the same two fields or the dropdown disappears the moment a saved
> conversation is reopened, which would read as a second bug. Three files,
> one new SSE field, one schema change to what a saved conversation stores,
> real work, correctly deferred rather than rushed this session.

**Why.** Asked for directly. The page mixes three activities in one column, and
the web panel is bolted on top of the message list.

**Shape.**

- **Chat**: plain grounded Q&A
- **Agent**: tool-calling with its own controls: which tools are allowed this
  turn, max rounds, visible plan/progress, and a stop that keeps what it already
  did
- **Browse**: web search results, reader view, page history

Cross-linking is the point: the agent hands a page to Browse, Browse hands a page
to the chat. Web-search gating should be independent, a Browse-only mode where
the section works even when the chat/agent `web_search` tool is off.

**On the "in-built browser".** In the browser-served app this can only be an
`<iframe>`, and most sites send `X-Frame-Options`/`frame-ancestors` that refuse
to load in one, it would fail on exactly the sites worth opening. Proxying and
rewriting pages server-side is effectively writing a browser, and re-introduces
every tracker the privacy work removed. So the reader view stays the web path,
and a genuine embedded browser belongs in the desktop shell, whose webview can
navigate anywhere. **This ties §3 to §7.**

---

## 4. Library tab: chats, documents, images, archive

> **Status: item 4 (the Library tab itself) is done, §36F/G built it and it
> now absorbed the Notes tab's Bin/Activity/Tags panels too, well past this
> section's original scope. Item 1 (drag-drop any file type onto the capture
> box, OCR on uploaded images) is now also fully done, OCR being the last
> genuinely open piece (ROADMAP.md item 30d). Item 3 (`archived_at`) is
> also done: `Entry`, `Conversation` and `Document` each carry the column
> (`core/database.py`, checked 2026-10-04).** This section read as entirely unbuilt
> before an earlier audit, which is exactly the kind of staleness that costs
> a session; check `routes_library.py` and the `Entry`/`Document`/
> `Conversation` models before assuming otherwise.

**Why.** Asked for directly. Everything that isn't a note lives only in its own
tab, and there is no archive at all.

**Order matters: images first, since the gallery is a view over what they
store:**

1. ~~**File uploads on notes**~~ **Built, see `frontend/js/attachment-actions.js`, `routes_files.py` `ATTACHMENT_SUFFIXES` and `routes_library.py`** (every sub-bullet below is struck or done). Original ask: **File uploads on notes, asked for again, directly: "I want to be able
   to upload files with notes."** Worth being precise about what's already
   there versus what isn't, since this is narrower than it sounds:
   - **Already exists:** images can be pasted or dropped into a note or
     document (this item, above), and `📎 Attach a file` stores an arbitrary
     file (PDF, `.docx`, anything) against a note and gives you back a
     download: so the storage layer and one upload path both already
     handle non-image files.
   - ~~**What's actually missing:** that attach path is a button, reached
     after the note exists, there's no drag-and-drop of an arbitrary file
     straight onto the capture box itself.~~ **Stale, already done.**
     `app.js`'s global `dragover`/`drop`/`paste` handlers match *any*
     `<textarea>` (including `#entry-content`) and already filter for
     `image/`, `application/`, `text/`, `video/` and `audio/`, not
     image-only: and attach every file in a multi-file drop, not just the
     first. A file-picker button (`#entry-attach-file`) reuses the same
     `handleFileUpload` for a third path. See the "ROADMAP.md Tier 2 §16c"
     comment right above `#entry-attach-file`'s listener in `app.js`, this
     was checked and closed a session ago; this bullet just never got
     updated to say so.
   - ~~**Genuinely still open:** a non-image attachment showed no preview in
     the note card~~ **Done, both halves.** `handleFileUpload` always wrote
     `![name](url)` (image markdown) regardless of file type, so a
     PDF/docx/etc. rendered as a broken `<img>` and its `onerror` handler
     reported it as **"filename deleted"**, actively lying about data loss,
     non-image files now get plain link markdown (`[name](url)`) instead.
     And that link now carries a type-specific Phosphor icon
     (`attachmentIconClass()` in `app.js`, keyed off the file extension for
     `/media/` uploads only: an arbitrary external link's extension isn't
     trustworthy enough to icon the same way) instead of reading identically
     to a plain URL.
   - ~~**A step further, genuinely new: extracting text from what's
     uploaded, not just storing it.**~~ **Done, see ROADMAP.md item 30d
     and HANDOVER.md's latest entry.** Local `pytesseract`/Tesseract, on a
     background thread, feeds the Library's own Image Gallery search (new)
     rather than the notes' FTS5 index this bullet originally pointed at,
     a `MediaUpload` isn't an `Entry`, so that was the honest integration
     point once the actual schema was checked, not the literal one this
     text guessed at. "What was on that whiteboard photo from March" is
     now answerable.
2. ~~**A bigger sketch board**~~ **Pointer:** built as the whiteboard (`frontend/js/whiteboard.js`, `routes_whiteboard.py`); what is left is
   [WHITEBOARD_PLAN.md](WHITEBOARD_PLAN.md) and `scratchpad/audit1005/features.md` section 4.
3. ~~**Archive.**~~ **Built** for notes, chats and documents (`archived_at`).
4. ~~**Library tab.**~~ **Built, see `frontend/js/library.js` (`LIBRARY_KINDS`) and `api/routes_library.py`.** One place showing stored images, documents, chats and
   archived items, with previews, sorting and search.

---

## 4a. A real whiteboard, not just a bigger sketch

**Built.** The structured canvas this section sequenced behind a raster version is
what shipped: cards, text boxes, shapes, images and ink on a pannable board, each its
own positioned row (`frontend/js/whiteboard.js`, `api/routes_whiteboard.py`), living
in the Library's Whiteboards gallery. **Pointer:** every open whiteboard question is
[WHITEBOARD_PLAN.md](WHITEBOARD_PLAN.md) and `scratchpad/audit1005/features.md`
section 4 (the gap matrix), section 5 (draw.io) and section 8 (the object library).
The raster-versus-structured reasoning that stood here is in this file's git history.

---

## 4b. Templates and base layouts (boards, maps, documents)

~~Asked for 2026-09-13, deferred out of the 0.3.0 PR.~~ **Built** (WHITEBOARD_PLAN decision 25): a board or map template is a board library item of kind `template` (`routes_board_library.py`, `library_ref {id, version}`, `POST` new board from a template), shown in the object library's "Yours"; documents keep their own gallery (`DOC_TEMPLATES`, editable). The record is HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)".

## 5. Documents

Checked against the running app, not assumed:

- ~~**Outline / table of contents**, reading time~~ **done.** `renderDocOutline`/
  `renderDocStats`, see HISTORY.md.
- ~~**Expand a note into a document**~~ **done**, leaves the note untouched
  and says so.
- ~~**Word-count goal**~~ **Done.** `promptDocWordGoal`/`#doc-word-goal` set a
  target, persisted per-document (`docWordGoal:<id>` in localStorage), with
  progress shown against it.
- **AI chat bar inside the document**, **Pointer:** [DOCUMENTS_PLAN.md](DOCUMENTS_PLAN.md) "Placed from INBOX, 2026-10-03 (INBOX 409)" closed the bar's design; the conversational shape (ask without proposing an edit) is `scratchpad/audit1005/features.md` section 11 Phase G. Partly there. `doc-ai-panel` already
  edits a selection or the whole document and shows the result as a proposal.
  What's missing is the *conversational* shape: ask a question about the
  document without it proposing an edit.
- ~~**A real document browser**~~ **Built, see `frontend/js/library.js:2941` (`renderLibraryDocuments`, the Library's Documents gallery).** The sidebar list is not a gallery
- ~~**Attach documents to notes**~~ **done, both directions.** The capture
  box's *Add to document* picker, a note's own 📄 chip/menu entry, and a
  document's list of the notes it draws on all share the same two
  `document_links` routes: see HISTORY.md.
- ~~**Document history**~~ **Built, see `core/database.py:1398` (`DocumentRevision`), `#doc-history-dialog` and DOCUMENTS_PLAN Phase 5 item 2.** Notes have `EntryRevision`; documents had no
  equivalent table, and the AI edit overwrote on accept

### Asked for this session, not yet built

A round of use produced four requests about documents at once, and they are
one direction rather than four features: *"I want the documents to be more
like using Obsidian or Notion."* Ordered by how much each one gets in the way.

- **A mini AI chat bar in the document editor.** **Pointer:** same row as the first bullet of this section (DOCUMENTS_PLAN INBOX 409; features.md Phase G). Asked for directly: *"a mini
  chat bar on the documents page to request the ai to do stuff, like write
  something, edit something specific (the whole document or current selection
  etc)."* This is the biggest of the four and the closest to already existing:
  `doc-ai-panel` edits a selection or the whole document and shows the result
  as a proposal, so the *editing* half is built. What is missing is the
  **conversational** half: a bar you type an instruction into, in place, that
  can either answer about the document or propose an edit to it, and that
  keeps the thread of what you have already asked. Two decisions to make
  before building it: whether it shares `/chat`'s conversation store (a
  document's thread is about the document, so probably its own), and whether
  an instruction with a selection active always means "edit this" (it should
  - ambiguity there is what makes an AI editor feel unpredictable).
- **Upload a file as a document, attached to a note.** Asked as *"I want to be
  able to upload a document to a note"*. Distinct from `📎 Attach a file`,
  which stores a blob against the note and gives you back a download: this
  would take a `.md` or `.txt`, make it a real Document with its text in the
  editor, and link it to the note in one step. The pieces exist: `/files`
  ingests uploads, `/documents` creates, `document_links` joins: so this is
  mostly a route that does the three together, plus deciding what to do with a
  `.docx` or a PDF (probably: refuse politely rather than half-convert).
  **Partly built, 2026-10-05:** `POST /documents/import` (`routes_documents.py:489`) extracts
  a .docx, .pdf, .csv, .md or source file into a Document (chat attach uses it,
  `chat-attach.js:435`), and a note's own 📄 picker links a document
  (`document_links`). **Next:** the note editor's attach path calling `/documents/import` then
  `POST /entries/{id}/documents` in one click (`frontend/js/attachment-actions.js`, `note-edit-panels.js`).
- **Obsidian/Notion editing: asked for again, more emphatically: "have all
  the features as well."** Worth being explicit about what "all the
  features" would actually include, since Obsidian and Notion aren't the
  same product and "all of both" isn't a coherent target. The editor is a
  `<textarea>` with a preview beside it today. What people mean by this
  request, roughly in order of how much each is missed:
  - ~~`[[wiki links]]` between documents~~ **Built (DOCUMENTS_PLAN Phase 4)** (notes already have them, the
    parser is in `renderNoteText`)
  - ~~a `/` command menu at the cursor~~ **Built, see `frontend/js/editor.js` and DOCUMENTS_PLAN section 18**
  - ~~drag-and-drop images that land as markdown~~ **Built (`![[photo.png|300]]`, `documents.js:5501`)**
  - ~~backlinks ("what links here")~~ **Built (DOCUMENTS_PLAN Phase 4, backlinks scanned on the server)**
  - ~~live-preview editing where the markup renders in place instead of in a
    second pane~~ **Built (the CodeMirror 6 engine, DOCUMENTS_PLAN Phase 2 and section 17, `doclivemd.js`)**, the one that would change the feel and also the one that
    means giving up the textarea; worth doing deliberately, and last
  - **Sub-pages.** **Next:** not in DOCUMENTS_PLAN and `documents` still has no `parent_id` (`core/database.py:1205`); needs a decision row there first, then an Alembic revision, `routes_documents.py` list/move routes and the sidebar tree in `documents.js`. Docs area, so it waits for the documents agent. Notion's documents nest into a tree; Tessellate's are
    flat. Worth deciding this one early rather than late, since it's a data
    model question (`documents` would need a `parent_id`) that every other
    item in this list is easier to build on top of than to retrofit under.
  - ~~**Transclusion: embedding, not just linking.**~~ **Built (`![[Doc#^id]]`, DOCUMENTS_PLAN Phase 4 item 2, `documents.js:3212`).** `document_links` already
    connects a note to a document, and `[[wiki links]]` connect document to
    document, but both are references you click through, not content
    rendered inline. Obsidian's `![[note]]` embeds the note's actual text
    where you put the embed. This is the feature that would make the
    notes/documents "two halves of a whole" framing actually true visually,
    not just at the data layer, worth building once backlinks exist, since
    an embed is close to a backlink that renders instead of just linking.
  - ~~**A full properties/database system is worth ruling out explicitly,**~~ **Decided: out of scope, as this item recommended** (document properties exist as light metadata, DOCUMENTS_PLAN Phase 3; no second data model). **A full properties/database system is worth ruling out explicitly,
    not leaving ambiguous.** Notion's defining feature is that a page can
    carry structured properties and be queried like a database row, that's
    a different kind of thing from a markdown document with metadata, and
    building it properly would mean a second data model living alongside
    notes' tags/categories rather than reusing them. Worth deciding this is
    out of scope on purpose (tags and categories already give notes
    lightweight structure; documents don't obviously need a second, heavier
    system) rather than something quietly missing from an "all the
    features" list that was never going to include it.
- ~~**Documents on the graph and the timeline.**~~ **Built, see `api/routes_graph.py:365` (`_add_document_nodes`, the Documents toggle `#graph-documents`) and `api/routes_timeline.py:102` (`KINDS` includes document; TIMELINE_PLAN Phase 4).** Asked as *"docs should also
  probably show on the graph and timeline"*. Both views are built around
  `Entry` and would need a second node/point kind. The design question is not
  technical: a document is not a note, and drawing it as one would say the
  wrong thing. On the graph it wants its own shape and to sit where its notes
  are (it is a hub over them, which is exactly what `document_links` records);
  on the timeline it wants to be a band or a marker rather than a dot, because
  a document is written over weeks and a note happens at a moment.

---

## 6. OpenAI-compatible backends: **done**

Built: the detail moved to [HISTORY.md](HISTORY.md) ("Retired from the live files, 2026-09-07"). Kept for its number.

## 7. Desktop packaging

**Windows installer: built, not yet run for real.** Asked directly which of
portable/installed/both, which platform(s) first, whether to pay for code
signing, and where to distribute, answers: installed (not portable),
Windows only for v1, unsigned for now (a certificate isn't worth it before
there's a user base to justify the yearly cost), GitHub Releases only. Built
on those answers: `packaging/windows/memorymap.spec` (PyInstaller, onedir:
onefile re-extracts itself on every launch, a bad fit for something meant to
open like a normal desktop app), `packaging/windows/installer.iss` (Inno
Setup, per-user install so an unsigned build doesn't *also* need an admin
prompt on top of the SmartScreen click-through), and a `build-windows-
installer` job on `release.yml` that builds and attaches the installer to
the GitHub Release a `v*` tag already creates. `core/config.py`'s
`_default_data_dir()` and `api/app.py`'s `FRONTEND_DIR` both needed a
`sys.frozen` branch: their existing path math assumes a `src/` layer a
PyInstaller bundle doesn't have, which would have pointed both at the wrong
directory silently.

**Honestly unverified**: this repo has no Windows machine to build or run it
on, so none of the above has executed for real yet, only reasoned through.
It ships from CI (windows-latest) on the next `v*` tag, which is a real
Windows build the moment it runs; what's unverified is specifically whether
that first real run succeeds without a fix. Worth watching the first
tagged release's Actions run rather than assuming green.

**"Does the installer stay up to date?", built: a check, not an auto-update.**
Asked directly. Answer: no, and it was never going to, a static installer
build has no mechanism to patch itself, and building one (differential
updates, a signed update feed) is a lot of infrastructure for a project at
this stage. What shipped instead, since the alternative is a user on a
six-month-old build with no way to know it: `update_check_enabled`
preference (off by default, same reasoning as `web_search_enabled`, see
`core/config.py`), a `GET /update/check` endpoint that compares
`tessellate.__version__` against GitHub's `releases/latest` tag numerically
(never lexically: "0.10.0" has to sort after "0.9.0"), and Settings → About
wiring: the checkbox, a "Check now" button, and a silent check on startup
that only ever toasts when a newer version genuinely exists. Two real bugs
were caught testing this live rather than trusting it once it typechecked:
`PreferencesBody` (routes_settings.py) never declared the new field, so
Pydantic silently dropped it from every PUT; and `get_preferences()` built
its response as an explicit field-by-field dict that never echoed the new
key back: the exact bug this same file's own comment already describes
happening once before, to `autonomous_tasks_enabled` and friends. Both fixed
and re-verified live (Playwright: toggle, reload, confirm it survives).

**Why.** Asked for: "run as a professional product".

**Recommendation: not Electron.** The app is Python + static files; Electron
would bundle a second runtime (~150 MB) and a Node toolchain to deliver what
`--desktop` already does in-process via pywebview, and Python would still need
shipping alongside it. Alternatives weighed: Tauri and Wails (Rust/Go shells,
tiny binaries, but neither solves shipping Python), Neutralino (immature), plain
PWA (already supported via `manifest.webmanifest` + `sw.js`).

**Plan, updated: some of this is now built, not still planned.** Hardening
the pywebview mode: **tray: built**, see §25. **Single instance is built**
(`__main__.py`, the owner's decision: one server per data directory). Native
menus, ~~graceful port fallback when 8000 is taken~~ (built, `__main__.py:811` `_port_holder` picks the next free port), and a first-run flow
specific to the packaged build are still open. **(needs owner)**: they need
the packaged build on a real machine. The "PyInstaller one-file" half of this
paragraph is superseded by the actual decision recorded above, **onedir**,
not onefile, because onefile re-extracts itself on every launch. pywebview's
webview is also where the genuine embedded browser from §3 becomes possible.

**Portable vs installed, worth deciding rather than defaulting into one.**
PyInstaller can build either, a one-file executable that runs from a USB
stick with `data/` beside it, or a real OS-integrated install (Start Menu
entry, `/Applications`, an uninstaller). They want different things from
`TESSELLATE_DATA_DIR`: portable mode wants data relative to the executable by
default (so the whole thing is one folder you can move); an installed app
wants a proper per-user data directory (`%APPDATA%`, `~/Library/Application
Support`, `~/.local/share`) so it survives a reinstall. Worth picking the
default deliberately per platform rather than the build script producing
whichever one falls out of the PyInstaller config first.

**Cross-platform status, since it was asked about directly** ("make
memorymap-ai cross-platform and compatible with linux and if possible mac as
well"): closer to done than the ask implies. `start.sh` already exists
alongside `start.bat`, and the app itself is Python + SQLite + a browser, none
of which is Windows-specific. What genuinely is Windows-specific: the two
`searxng_manager` fixes in §8b (`os.kill(pid, 0)` terminating instead of
checking, `rmtree` failing on git's read-only objects) are guarded to only
run their Windows branch, so they should be harmless elsewhere, but that is
still unverified on real macOS/Linux hardware rather than reasoned from the
code: the honest status is "should work," not "confirmed." The PyInstaller
builds above are the part with no cross-platform equivalent yet at all.

- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 

---

## 8. Open bug list

Every bug this section originally listed, the launcher breaking on a folder
rename, a theme picker whose layered defaults silently cancelled part of
each new theme, the Lagoon/Shallows palette refinements, background tasks
showing nothing while SearXNG started, the cramped AI emblem, the dashboard
widgets missing until a tab switch, plus a long table of "reported as / what
it actually was" fixes (numbered lists, chat-bubble overflow, "Invalid
Date", CSS specificity ties, sketches not opening from the graph, web search
silently returning nothing) and the bugs found incidentally while fixing
those: has been reproduced in Chromium and fixed. Full detail, including
*what each report's real cause turned out to be* (the expensive part to
repeat if it isn't kept), is in HISTORY.md.

**From the ideas parking lot, never formally triaged.** Reported informally
(`IDEAS.md`) rather than reproduced in a browser yet, worth the same
ten-second grep-first check as everything else in this document before
anyone spends a session on them. (The other four of the original five were
checked 2026-10-04 and are in HISTORY.md, "Moved from the backlog".)

- **A note filed under the wrong category by a wide margin** ("ai is cool" filed
  under Sketches): **built 2026-10-05**, HISTORY.md ("backlog-1005"). A note under
  four words files by meaning only when its nearest filed note is 0.72 close
  (`janitor.SHORT_NOTE_MIN_NEIGHBOUR`), measured with the real embedding model.

**The lesson worth keeping.** Four of these were "this control does nothing",
and in three of the four the control was working perfectly, the write landed
and was then overridden by CSS source order, a status poll, or a hidden
section. Reading the handler will not show you that. Reproduce in a browser and
measure the *computed* result; it is faster than reading, not slower. The
recurring causes are now written up as invariants in `docs/ARCHITECTURE.md` §10.

---

## 8b. Web search: two Windows bugs found, and what is left

~~**Port 8888 being taken was a dead end.**~~ **fixed.** `start()` now
settles a port first (the wanted one, else 8080/8081/8890/8899, or
`TESSELLATE_SEARXNG_PORT`).

**SearXNG itself now installs, starts, answers its JSON API, passes
`websearch.probe_searxng`, and returns real results on a user's own
Windows machine: confirmed, not deduced.** Six real bugs stood between
"install path exists" and that (three platform-independent: a Windows-only
`git clone` colon-in-filename failure, `pip install -e .`'s isolated-build
`msgspec` import error, and the `tracker_url_remover` plugin dying at boot
on any offline/proxied machine; three Windows-only: `os.kill(pid, 0)`
actually terminating the process instead of probing it, a stale
`is_checkout()`/`shutil.rmtree` interaction that made a failed reinstall
reproduce itself, and the POSIX-only `import pwd` in `searx/valkeydb.py`).
Full diagnosis of each, and the fix, is in HISTORY.md, worth reading in
full if SearXNG install/start is ever reported broken again, since the
shape ("Windows-only", "happens before SearXNG writes a line") is a strong
signal for which of the six it is.

Also present, from earlier sessions: a `↻ Reinstall` button (wipes the venv
and checkout, keeps `settings.yml` and its secret key) and a port line saying
whether 8888 is free, held by a working SearXNG, or held by something else.

**A deliberate security pass, rather than more one-off fixes.** Asked
broadly: "full security sweep and analysis… must be fully private, hack
proof, and secure… web browsing should be as private, secure, and
untrackable as possible", which is this section's whole subject already,
just not gathered into one pass. What exists today: the CodeQL alert list is
closed, the DNS-rebinding TOCTOU on both the reader and the SearXNG search
path is closed, redirects are re-checked hop by hop rather than trusted,
private notes are encrypted and excluded from every AI tool, and CodeQL
runs on every push plus weekly. Brute-force protection on the unlock gate,
a tight CSP, the scrypt KDF behind private notes, and cross-origin
protection on the local API are all **done**, see HISTORY.md and §20.
What a deliberate pass would add on top, parallel to §19's accessibility
audit:

- A dependency-vulnerability sweep (`pip-audit` / `npm audit` equivalent for
  the vendored JS, since nothing currently checks either), and a fresh look
  at this section's own three easy-to-break rules (§8b's opening) to confirm
  nothing has quietly regressed since they were written down.
  **Next:** nothing in `.github/`, `scripts/` or `tests/` runs `pip-audit` (checked 2026-10-05); the security agent owns it with `scratchpad/audit1005/security.md`. An offline test over `frontend/vendor/*/` version stamps against a pinned advisory list is the vendored-JS half.
- **Search-specific items** now live in §13, since SearXNG went from "being
  built" to "actually running" this pass.

---

## 9. The graph: make it a tool, and give it a look

**Why.** Asked repeatedly: "expand on the capabilities of the graph", "more
utility and ways to use and visualise my notes", "it's still kinda plain, it
needs more life and design style". `main` made it keyboard-operable; it is still
a plain force-directed blob that doesn't fill its own panel.

**Layouts: the shape the notes are arranged in.** Asked for directly: "can
you add different types of graph views… like tree graph diagrams and the
like". These are separate from *styling*: a layout decides where a note goes,
a style decides what it looks like once it is there. Layouts first, because a
force-directed blob is the thing that makes the graph hard to read, and no
amount of styling fixes it.

The notebook has three different structures in it, and each one wants a
different picture:

| Structure | Where it comes from | Layout that shows it |
| --- | --- | --- |
| Hierarchy | category → note, and `parent_id` threads | tree, radial tree, treemap, sunburst |
| Network | `entry_links` (wiki links, AI links) | force, arc diagram, adjacency matrix |
| Sequence | `created_at`, `entry_dates` (§10A) | timeline-graph, growth animation |

- ~~**Tree**~~ and ~~**radial tree**~~ **built**, then re-fixed after a
  reported readability bug (both were first sized to the panel's raw
  dimensions rather than by what a label needs, see HISTORY.md for the
  `nodeSize`/ring-by-depth fix and the three label-collision bugs it also
  found).
- ~~**Mind map from one note**~~ **Built as the local map, see `api/routes_graph.py:900` (`graph_local`) and [GRAPH_PLAN.md](GRAPH_PLAN.md) "Built, Phase 4 (utility), part two: the local map".** Pick a note as the root and lay everything else
  out by hops along `entry_links`. Different from the tree above: the
  hierarchy there is filing, here it is connection.
- **Treemap / sunburst**: area as weight, so a category with 200 notes looks
  like one. Best for "where does my writing actually go?", and the only layout
  here that answers a question about proportion.
  **Next:** a new layout is one `layoutHierarchy`-style function in `frontend/js/graph.js` (`graphLayout()`, line 133, reads the `graph-layout` radio in `index.html:3410`), drawn by `graph-canvas.js`; no row in [GRAPH_PLAN.md](GRAPH_PLAN.md) yet, so add a decision there first. Graph area, owned by the graph agent.
- ~~**Arc diagram**~~ **built, on the filing hierarchy rather than
  `entry_links`** (a deliberate departure from this bullet's original "links
  as arcs" framing: tree and radial already draw the *filing* hierarchy, and
  a links-as-arcs view is still a real, different, unbuilt layout). Verified
  in Chromium against a seeded notebook, see HISTORY.md.
- **Adjacency matrix**: no crossing edges at all, so it stays readable when a
  force graph has turned into wool. Worth it only once there are hundreds of
  links.
  **Next:** a new layout is one `layoutHierarchy`-style function in `frontend/js/graph.js` (`graphLayout()`, line 133, reads the `graph-layout` radio in `index.html:3410`), drawn by `graph-canvas.js`; no row in [GRAPH_PLAN.md](GRAPH_PLAN.md) yet, so add a decision there first. Graph area, owned by the graph agent.
- **Timeline-graph**: the graph laid out left-to-right by date, links as
  arcs. §10's Timeline tab does the axis; this would do the axis *and* the
  links, which is the one thing neither view has.
  **Next:** a new layout is one `layoutHierarchy`-style function in `frontend/js/graph.js` (`graphLayout()`, line 133, reads the `graph-layout` radio in `index.html:3410`), drawn by `graph-canvas.js`; no row in [GRAPH_PLAN.md](GRAPH_PLAN.md) yet, so add a decision there first. Graph area, owned by the graph agent.
- **Subway map**: orthogonal edges, categories as lines. Beautiful and
  genuinely hard: it needs edge routing, which is real work rather than a
  layout call.
  **Next:** needs an edge-routing pass (orthogonal segments avoiding node boxes) in `graph-canvas.js`; the hardest of the layouts, do last. Graph agent's area.

**Styling: the same layout, dressed differently.** These are skins over
whichever layout is picked, not layouts of their own:

- **Galaxy / starfield**: notes as stars sized by access count, links as
  faint filaments. The dashboard's "notebook constellation" widget already
  proves the aesthetic works.
  **Next:** a skin is a colour and size rule over the existing layout (`graph-canvas.js` draw pass); reuse `renderArtWidget`'s starfield palette in `dashboard.js`. No row in [GRAPH_PLAN.md](GRAPH_PLAN.md); add a decision there first.
- **Sea chart**: islands per category, notes as landmarks, links as shipping
  routes, unlinked notes adrift. Parchment palette pairs with it.
  **Next:** same seam as the starfield skin above, plus a parchment token pair in `00-tokens-shell.css` (DESIGN.md recipe index first).
- Plain force-directed stays the default; everything else is a picker.

**Fit and framing. Built, see `frontend/js/graph.js` (`fitGraphToView`, the zoom strip) and `graph-canvas.js` (`graphMinimapFrame`; [GRAPH_PLAN.md](GRAPH_PLAN.md) Phase 1).** It should size to its panel and re-fit on resize, with
zoom-to-fit, zoom controls, and a minimap for large notebooks.

**Utility: checked against the code 2026-10-04.** Built: paths between two
notes (`path_between`, the trace in `graph.js`), orphans and hubs, a link by
dragging one node onto another, the timeline scrub, PNG export of the view,
filters, and `related_notes(id, depth)`. Not found by grep, **since built** (`api/routes_graph.py:1042`, GRAPH_PLAN KG6: named topics inside the islands, a rename stored under `TOPIC_NAMES_KEY`, a cached model summary per topic): **the AI naming a
cluster** (cluster detection exists, a name from the model does not).
GRAPH_PLAN.md owns the rest of this section.

---

## 10. Timeline tab, and time-aware notes

**Why.** Asked for directly, and it is the most substantial new idea in the
backlog. Notes say "today", "yesterday", "last week", "two days ago", phrasing
that is correct when written and misleading forever after. Today nothing records
what those phrases *resolved to*.

**Three parts. The first two are done, the third is the one asked for again,
more directly, and is not built yet:**

~~**A. Resolve relative time at capture.**~~ **done.** Every note's temporal
phrases are resolved when it is saved and stored in `entry_dates` with the
phrase beside the date; `entry/timewords.py` is deterministic regexes and
arithmetic, not a model call. Shown as a chip on the note rather than marked
up inside the text. See HISTORY.md for the full list of handled phrasings.

**Still open from A:** tagging notes that contain relative time so they are
findable as a class, and nudging on stale ones ("this said 'tomorrow' three
weeks ago: did it happen?"). Both are queries over `entry_dates` now that
the data exists. **(needs Opus)**: the nudge is a surface to design; TIMELINE_PLAN.md
owns the rest of this section.
**Next:** the tag half is a query over `EntryDate` (`core/database.py`, read in `api/routes_timeline.py:484`) for rows whose phrase is relative and whose date is past, offered as a Library chip; the nudge is a card in `ai/resurface.py`'s feed or the Night widget (`dashboard.js` `renderNightWidget`). No TIMELINE_PLAN row; add one first.

~~**B. A Timeline tab.**~~ **built, first version, and it is a grid, on
purpose, for what it's for.** A time axis across, one band per category or
tag down the side, a bucket size you pick, drawn as a CSS grid (not SVG) so
it scrolls/tabs/reads-aloud for free, capped at eight bands plus "Everything
else".

~~**C. A branch/line view**~~ **built, asked for again, more directly,
because B reads as a calendar rather than a timeline.** A spine plus one
lane per band, connected by a stub at each band's first note; the branch
source is category/tag (not §9's cluster detection: see HISTORY.md for
why), and "rejoins the spine" was deliberately not built (a branch runs its
full lane length, which is a more honest shape than implying a thread
concluded). A real hit-testing bug (an invisible connector stub eating
clicks meant for the dots above it) was found and fixed verifying this
live. Verified in Chromium against seeded notes across four categories and
a reply thread; the one thing not verified is the tick-label spacing
against a notebook that genuinely spans weeks or months (all seeded notes
landed on the same day). No new table: reads `entry_dates` (§10A) and the
existing category/tag grouping; the only new state is a `localStorage`
view preference.

**Still open in B (the grid view; the view has since become a feed, TIMELINE_PLAN Phases 1 to 3):**

- **Events as bands.** **Next:** no `events` calendar table exists (the `events` in `core/events.py` is the change log, a different thing); it needs an Alembic revision, `routes_timeline.py` `KINDS` (line 102) gaining `event`, and `add_event`/`list_events` tools (BACKLOG section 14); TIMELINE_PLAN has no row for it. The shape this slots into: one more `group` value, once
  there is an `events` table. Places and themes can be derived from what is
  already stored; events cannot.
- ~~**Zoom from days to years as a gesture**, rather than a bucket picker.~~ **Built as a scale choice, see `frontend/js/timeline.js` (`timelineScaleChoice`: Auto, Day, Week, Month, Year; TIMELINE_PLAN Phase 3, scrubber and scale).** A wheel or pinch gesture is not built; the picker is the deliberate shape (`timeline.js:299` records why a dropdown beats a segmented row at large zoom).

**Data shape:** a new `events` table (`title`, `at`, `precision`, `kind`,
`entry_id?`, `source`), plus `entry_dates` for resolved expressions. Both
additive.

---

## 11. Performance, accuracy and AI efficiency

### Headroom: evaluated, not adopted

Asked: *"is it worth trying to analyse and implement something like headroom
for token efficiency?"* ([headroomlabs-ai/headroom][hr]: Apache-2.0, 62k
stars, active). It compresses tool outputs, logs and RAG chunks before they
reach the model: 60–95% off JSON, 15–20% for coding agents, with benchmark
accuracy held. It is a good project. It is the wrong fit here, for three
reasons that are about **this** app rather than about it:

1. **There is no token bill.** Ollama runs on the user's own machine, so a
   token costs latency and context window, not money. Headroom's headline
   numbers are savings on a metered API.
2. **It would compete for the same CPU.** The compression path wants ONNX
   Runtime and a transformer of its own, running immediately before the local
   LLM on the same hardware. Saving 1–2k tokens of prefill by spending an
   inference pass is very likely net-negative on wall-clock for a 7B model on
   a laptop: and it needs AVX2, which is not a promise this app can make.
3. **The JSON it would compress is the JSON that cannot be compressed.**
   This one was worth measuring rather than assuming, and the measurement
   moved the answer. A representative agent prompt, ten retrieved notes, two
   turns of history, focused tools:

   | Part | Chars | Share |
   | --- | ---: | ---: |
   | System prompt (prose) | 2,521 | 34.4% |
   | History (prose) | 77 | 1.1% |
   | Notes + question (prose) | 1,381 | 18.9% |
   | **Tool schemas (JSON)** | **3,340** | **45.6%** |
   | Total | 7,319 | |

   So the prompt *is* nearly half JSON, more than expected. But that JSON is
   the **tool schemas**, and Headroom compresses tool *outputs*, logs, files
   and RAG chunks. A schema is a contract the runtime parses to constrain the
   model's tool calls; compress it and the calls stop being valid. It is the
   one JSON block in this prompt that has to go verbatim.

   What is genuinely in scope: the notes (18.9%: this is the RAG-chunk case
   Headroom is built for) and the tool results appended during a loop, which
   are already hand-shaped summaries (`_note_summary`: id, preview, category,
   tags, dates). At its own headline 60% on the addressable part, that is
   roughly 11% off the prompt, real, but not the 60–70% the numbers suggest
   at a glance, and not worth ONNX Runtime to get.

   **The 45.6% is still the thing to attack, just not with compression.**
   `focus_for` already took it from 10,215 to 3,340 characters. Getting it
   lower is more schema pruning: shorter descriptions, fewer tools per focus,
   dropping parameters with obvious defaults. That is the highest-leverage
   work left in this section and it costs nothing but care.

Set against a **hard** cost: ONNX Runtime plus a model download, in an app
whose whole proposition is offline, self-contained and light, one that
vendors d3 and p5 locally rather than take a CDN.

**What was worth taking from it, and cost nothing:**

- ~~**Prefix-cache alignment** (their CacheAligner)~~ **done, and it found a
  real bug.** The idea is to keep the front of the prompt byte-identical so
  the provider's KV cache survives. Checking ours against that: the system
  prompt carried `local.isoformat()`, *microseconds*, above the history and
  the notes. Every round of every turn differed from the last, so Ollama's
  prefix cache could never hold anything below that line, and each round of a
  tool loop re-read the entire prompt. Now to the minute, which is identical
  across the rounds of one loop and still correct for everything the app does
  with it ("remind me in 10 minutes" is not resolved to the second).
- ~~**Reversible compression** (their CCR: send a short form, let the model
  fetch the original on demand)~~ **done.** A note now goes into the prompt
  capped at `MAX_NOTE_CHARS` (900), cut with a marker naming the call that
  reads the rest: `… [cut: call get_note(7) to read it in full]`. Safe only
  because the model can undo it, which is the whole idea, and the tools guide
  already told it to call `get_note` before quoting. Most notes are a line or
  two and are untouched; ten notes of 4,000 characters used to be 40,000 and
  now fit the budget.
- ~~**Verbosity steering.**~~ **Built, see `ai/presets.py` (Quick, Normal, Detailed: `max_output_tokens`, `temperature`, `think`) and the same three presets in the Chat tab and Settings (`index.html:1712`).** Output tokens are half the latency and are not
  budgeted at all. A style hint already exists; a length hint does not.
  Asked for as a bigger idea, a **quick / normal / detailed** picker on chat
  and agent turns, where quick trims the length hint (and, on a model that
  supports it, disables its own "thinking") and detailed asks for the
  opposite, with the option to pin a specific model to each level rather
  than always using whichever is set in Settings → Models. That's a UI and a
  prompt change, not a new capability, the pieces (a style hint, a
  per-purpose model already existing for chat/embedding/utility) are already
  there; this is a preset over them.
- ~~**Temperature and sampling parameters, not just length**~~ **Built, see `ai/sampling.py` (the model's own `/api/show` parameters, then the task preset, then the user's sparse override) and `ai/presets.py`; all three sub-bullets below are covered, the per-model half by `ai/model_cards.py` and the capabilities table in Settings, Models.** Asked for
  directly. "Is it a good idea to change model temperature and other
  parameters, as well as the amount of thinking, based off the type of
  task?" Yes, and it's the same preset idea as the bullet above, widened:
  quick/factual work (recalling a note, answering "when did I write X")
  wants low temperature and a short or disabled thinking budget; open-ended
  work (drafting, brainstorming) wants both opened up. Ollama's
  `/api/chat` already accepts `temperature`, `top_p`, and: on models that
  support it: a `think` toggle or budget per request; none of this needs a
  new capability from the model side, only a place in the request that
  today always uses whatever the default is.
  - **Manual first, automatic second, same ordering logic as model
    routing below, and for the same reason.** A per-mode set of parameters
    the person picks (or accepts a sensible default for) is honest about
    being a preset. Auto-adjusting parameters *by task* needs the same
    "how hard is this turn" judgement call that model routing does, so it
    inherits the same risk of being wrong confidently rather than
    obviously.
  - **Auto-adjusting *by model*, though, is worth doing regardless of the
    task question, because it's not a guess.** Not every installed model
    supports a thinking toggle, and the ones that do vary in what "off"
    means for reasoning quality on a given task. `Settings → Models`
    already knows which model is loaded, extending that to record what
    the model actually supports (thinking toggle, its context length, a
    sane default temperature) means a quick-mode preset can *fail closed*
    gracefully on a model that doesn't support the setting instead of
    sending a parameter Ollama silently ignores or errors on, which is a
    real gap regardless of whether task-based auto-routing ever happens.
- **Dynamically switch models by task complexity.** **Next:** the manual per-mode assignment this item says to build first exists (`openFeatureModelSheet`, `frontend/js/ai-tools.js:698`, `ai/provider.py` per-purpose model); the automatic half is a design call for the owner (a cheap difficulty estimate is wrong sometimes) and stays open on purpose. A related but separate
  ask: "optional," and worth keeping optional: a short factual question
  routed to a small fast model and an agent job routed to a larger one,
  automatically. The honest version of this needs a cheap way to estimate
  "how hard is this turn" before picking a model, which is itself a model
  call or a heuristic that will be wrong sometimes, worth prototyping as a
  manual per-mode assignment (the bullet above) before attempting to guess.
- **A model comparison / test-run feature**, **Pointer:** WORLD_CLASS_PLAN I8 "The model bench" (H3, row 21; `model_bench` switch in `ai/facts.py:85`, no `ai/bench.py` yet). Asked for directly: "test and
  compare different models for use in the application so you can choose the
  best one."** This is the eval harness below, pointed at a different
  variable. The harness already needs a fixed set of representative prompts
  to catch regressions over *time*; running that same fixed set against
  every installed model in one pass, and showing the results side by side,
  tokens, latency, and (for the ones with a known-good answer, like "what
  did I write about X") whether it actually got it right, answers "which
  model" instead of "did this get worse." One dataset, two use cases: a
  scheduled or CI-triggered run watches for regressions on the model
  currently in use; a manually-triggered run compares candidates before
  switching. Worth building as one feature with two entry points rather
  than two separate ones, since duplicating the prompt set would mean they
  drift out of sync with each other.

**Before any more of this: measure.** §11a was done by counting characters of
tool schema, which is why it worked. "A 3-turn chat shows 8.7k tokens" is not
yet broken down into system / tools / history / notes / question, and until it
is, the next optimisation is a guess.

[hr]: https://github.com/headroomlabs-ai/headroom


**Why.** Asked: "make sure all the code, processes, and AI usage is fully
optimised and efficient", and "more ways to make the program and AI more
accurate, usable, capable, and faster".

**Measure first**: there is no profiling in the repo, so where a chat turn
spends its time is currently a guess.

- **Prompt reuse.** Every agent round resends the whole message list;
  `keep_alive` is set now (`OllamaClient`, 30 minutes, checked 2026-10-04);
  prompt-prefix reuse is not verified. **(needs Opus)**: it needs a real model.
  **Next:** `scratchpad/llama-dev.sh serve`, then compare `prompt_eval_count` on round 2 against round 1 of one agent turn through the log line in `ai/agent.py` ("prompt composition"); the minute-rounded clock (section 11 above) is what makes a hit possible. Real model only.
- ~~**Cap tool output.** Return previews by default, full text only on request.~~ **Built, see `ai/agent.py:339` (`TOOL_RESULT_BUDGET_CHARS`, applied at line 2558) and the 900-character note cap with its `get_note` marker (section 11, "Reversible compression").**
- ~~**Hybrid retrieval** (semantic + keyword, reciprocal-rank fusion)~~ **done**
  - HISTORY.md's "Retrieval reads the question before searching it": both
  searches run and their rankings fuse by RRF, not either/or. Flagged stale in
  this session's backlog audit; was still marked open here.
- **Re-ranking** with a small cross-encoder over the top-20, behind a setting. **Next:** nothing in `src/` re-ranks (checked 2026-10-05); the seam is the fused list in `search/engine.py`, a utility-model scoring call (the section 95 item 7 shape, no new dependency) behind a Settings switch with its '?', measured on `tests/eval/` before it ships. Retrieval area; real model to judge it.
- ~~**Batch embeddings**~~ **Built 2026-10-05, see `ai/embeddings.py` (`EMBED_BATCH`, `EmbeddingService.store_for_entries`, used by `_backfill_missing`) and `ai/model_manager.py` (`_reindex_pass` walks the notebook in batches of 16 and checks for a cancel between them); `tests/test_embedding_batches.py` and `test_embedding_batches_reindex.py` count the calls.** The backfill embedded one note at a time.
- ~~**Context warning** as the window fills~~ **Built, see `frontend/js/chat.js:425` (the meter's tooltip warns past 80% and names Compress, with the per-stage composition).** The per-turn cost is already shown.
~~- **A per-chat token/context meter the user can actually see.**~~ **Built**
  (ROADMAP §88.4 item 4). Asked twice, once directly ("a better way to track
  tokens and other things") and once from the outside review ("prompt
  inspector, token counts, latency breakdown"). §11a already measured this
  server-side (prompt composition logged per round, chars only, Settings →
  Logs only): now also attached as a token estimate to the chat metadata
  line's own window-fill tooltip, exactly the "~1.4k tokens this turn, 3.1k
  fixed overhead" shape asked for, per stage (system/tools/history/notes)
  rather than a single fixed-overhead number.
- **An eval/benchmark harness tied to changes here.** **Pointer:** WORLD_CLASS_PLAN B5 "Evals as fixtures" and I8; `tests/eval/`, `pytest -m evals` and `scratchpad/llama-dev.sh` exist (CLAUDE.md section 4). Every optimisation in
  this section so far has been measured by hand, in one session, against
  whatever the person doing it happened to type. A small fixed set of
  representative prompts (a few notes, a few questions, a skill run) that CI
  or a pre-release check can run against a real Ollama model and report
  tokens/latency/answer-still-correct would catch a regression before a user
  does. The outside review's suggestion that actually survived, not because
  of any specific tool, but because "measure first" is already this
  section's own rule (§11a) and there's no repeatable way to do it yet. The
  same fixed prompt set is also what the model-comparison feature further
  down this section runs, against every installed model instead of just the
  one in use: one dataset, watching for regressions over time and
  differences across models with the same tool.
  - **Worth tracking retrieval quality specifically, not folding it into
    "answer-still-correct."** A wrong answer can come from the model
    reasoning badly over the right notes, or from search handing it the
    wrong notes to begin with, those are different bugs with different
    fixes, and a single pass/fail per prompt can't tell them apart. A known
    query with a known correct note (or set of notes) lets the harness
    check "did search find the right thing" separately from "did the model
    say the right thing," which is what actually lets a hybrid-search or
    re-ranking change (§11) be judged on its own rather than blamed on or
    credited to whatever model happened to be loaded.

**§11a: token usage in chats.** Asked directly: "is there a way to reduce
excessive token usage in the chats?" A three-turn conversation showed 8.7k
tokens. Where it goes, cheapest fix first:

- Retrieved notes are re-sent in full on every turn, including turns that are
  a follow-up to the previous answer and need no new retrieval at all.
- `MAX_CLIENT_HISTORY` turns of prior Q&A go up each time, whole.
- Tool results accumulate within a turn (already capped by
  `TOOL_RESULT_BUDGET_CHARS`, but the cap is generous at 24k characters).
- The system prompt is long and grew again this session; it is re-sent every
  round of every turn, which is where Ollama's prompt-prefix reuse and
  `keep_alive` would actually pay.

**Half of this has now been measured, and the answer was not where anyone was
looking.** The *fixed* overhead, system prompt plus every tool schema, sent
before a word of the question, the notes or the history, on each of up to
`MAX_ROUNDS` rounds: is ~12,400 characters, about **3,050 tokens**. Of that,
**9,957 characters (77%) is the tool schemas**, not the prose. Trimming the
guide was the smaller half by a wide margin.

`agent.PROMPT_BUDGET_CHARS` now caps it and `tests/test_prompt_budget.py`
fails the build if it drifts past, because this grows invisibly: every tool
added costs the same budget and nothing else in the suite would notice.

**Why it matters more than the arithmetic suggests.** Ollama defaults to a
4096-token window unless the model declares otherwise, and overflow is dropped
from the *front*: which is the system prompt. A 3B model (granite4.1:3b,
llama3.2:3b, qwen3.5:2b: the ones this is aimed at) that overflows therefore
stops knowing it has tools at all, and reports as **"the AI won't use
tools"**, which is the hardest possible symptom to trace back to a long
prompt. Settings → Tools is the user-facing escape hatch, and there is now a
test proving that switch reaches the wire rather than only the executor.

**The remaining win is offering fewer tools per turn, not trimming more
words.** 28 schemas go up every round whether the question is "how many notes
do I have" or "remind me to call mum". A relevance filter: or a small
always-on core plus an opt-in rest, is worth more than anything left in the
prose. Do it before §21 adds skill tools to the same budget.

Still unmeasured, and still worth measuring before cutting: which of the
*variable* costs above dominates a real 3-turn chat. Log the prompt-token
count per round. Summarising older history is the usual answer, but it costs a
model call, so it should be the last resort rather than the first.

**A shape for that last resort, not a decision to build it yet.** Odysseus's
`context_compactor.py` triggers at 85% of the model's reported context
window and self-summarises older turns via the same LLM into a structured
block, trimming harder below an 8k-token window; see ANALYSIS.md's
"Odysseus read deeply, 2026-09-21" section, item 1, for the full read and the
size/risk call (M, take the idea, measure it on a small model before
trusting it).

---

## 12. Does the AI know it is an agent?

**Why.** Asked: "does it know it is an agent and can use tools and skills freely
and in multiple turns if necessary?" and later, "I need agents to use tools more
and better if they are required."

**Honest answer: partly.** `TOOLS_GUIDE` says tools exist and forbids claiming a
save that didn't happen. The loop runs to `MAX_ROUNDS = 6`. What it is *not*
told:

- That taking several rounds deliberately is expected, plan, act, check, answer
- That skills exist at all (the tools are there; the prompt never mentions them)
- What to do when a tool fails, the error is returned with no guidance, so
  small models give up or repeat the same call
- That a search snippet is rarely enough and `read_url` exists
- What the user can already see (the step timeline), so it stops re-narrating

**Done since.** `TOOLS_GUIDE` now says that taking several turns is expected
("look something up, read what you found, look up anything still missing, then
answer"), that a search result is a clipped sentence and `read_url` exists,
and that the user can already see the tool timeline so it should stop
narrating its process back to them.

Failed tool calls now carry a `what_to_do` field matched to the failure, a
missing id says to search rather than guess another, a disabled tool says to
stop calling it, bad arguments say to re-read the schema and retry once, and
an identical call that fails twice is told so explicitly. Previously a failure
was a bare `{"error": …}`, and small models either apologised and stopped or
looped on it until the round limit ran out.

**Still to add:** an explicit `plan` step rendered at the top of the timeline
(build it with §21, which needs the same structure); a "required tools" hint
for requests that clearly need one; and a nudge when the model answers a
notebook question without having searched.

**Checked 2026-10-05:** the plan step is built (`make_plan`, ticked steps in the timeline). **Pointer:** the other two (a required-tools hint, a nudge when a notebook question is answered without a search) are WORLD_CLASS_PLAN B5's planner and verifier ("Open: pre" conditions); harness agent's area.

**Note the ordering.** None of this fixes "the AI won't make me a skill",
that fails because `save_skill` can only store a prompt string, so there is
nothing for a better-instructed model to call. §21 first.

---

## 13. Web search effectiveness

**Now that SearXNG actually works (§8b), what's left is refinement, not
bug-fixing**: asked for directly: "the whole search UI just needs
refinement, and make sure that the search methods are as secure and private
as possible." Split into the two things actually asked for.

**Quality and UX:**

- **Query expansion**: two or three phrasings, results fused. **Next:** `search/websearch.py:329` (`search_web`) takes one query; add a rule-based variant first (drop stop words, quote the longest noun run) and fuse by URL with the cache key in mind (`_CACHE`); a model-written phrasing is the second step and needs a real model to judge.
- ~~**Read before answering**: tell the model a snippet is rarely enough~~ **Built, see `ai/agent.py:415` (the tools guide says a result is a clipped sentence and `read_url` exists).**
- ~~**Cite sources** with the domains actually read~~ **Built, see `ai/agent.py:911` (`_tool_sources`: every `web_search` and `read_url` call contributes `{title, url, snippet}` rows to the answer's Sources panel).**
- ~~**Per-turn result cache**~~ **Built, found by checking, not assumed
  missing.** `websearch._CACHE`/`_cache_get`/`_cache_put`, keyed on
  `provider::searxng_url::query::limit`, a small in-process dict with the
  simplest correct eviction (clear it all once it's full) rather than a real
  LRU, which this cache's size doesn't need.
- ~~**SearXNG as the recommended default** once §2's install path
  works~~: the install path works now (§8b); worth actually flipping the
  default and updating the README/onboarding copy that still frames it as an
  advanced option
- ~~**Say which engine answered.**~~ **Built, found by checking, not
  assumed missing.** `websearch.answered_by()` returns a label plus a
  plain-English privacy note per provider ("SearXNG: your own instance,
  the query stayed on your machine" vs. "DuckDuckGo: a third party saw
  this query, but not your notes"); `routes_websearch.py` attaches it as
  `answered_by` on every search response, including a zero-result one on
  purpose ("no results" and "no results *from DuckDuckGo*" are different
  facts); `app.js`'s web-search status line already renders both the label
  and the detail beside the result count.
- ~~**Result cards worth reading, not just clicking.**~~ **Built, see `frontend/js/chat.js:1277` (`webResultMark`, the host above the title, the engines that found it, the snippet); the matched words are marked inside the snippet since 2026-10-05 (`webQueryTerms`, `highlightInto`; `tests/test_web_result_highlight.py`, `scratchpad/ui-sweeps/bl1005-webhighlight.js` at 1440 and 390, light and dark).** A title and a link today;
  a domain/favicon and a snippet with the matched terms highlighted would let
  someone judge relevance before opening the reader view, the same reasoning
  search engines converged on decades ago. **(needs Opus)**: a design pass;
  note that `chat.js` already draws a letter tile instead of fetching a real
  favicon (a fetch would tell the site someone searched), so any card keeps that
- ~~**Open a result straight into the reader**~~ **Built, see `frontend/js/chat.js:1351` (the title opens `openWebReader`)** without a second round trip,
  ties to §3's Browse sub-tab, which is the natural home for this
- ~~**Distinguish *why* zero results came back**~~ **Built, see `search/websearch.py:383` (rate-limited and engine-down raise different `WebSearchError` text, shown from the 502's `detail` in `routes_websearch.py:76`) and `frontend/js/chat.js:1564` ("No results from <engine>: try different words").** In the UI itself, not just the
  log: rate-limited, engine down, genuinely nothing found are three
  different situations and currently look identical to the person searching
- **Deciding *when* to search, not just how well it searches once asked.**
  Asked for as "better agentic web search through chat", read as being about
  judgement, not just result quality. Today `web_search` is one tool among 28
  the model can choose or not; nothing measures whether it reaches for it
  when a question is actually time-sensitive ("what's the latest version of
  X") versus when it should trust the notebook or say it doesn't know. That's
  a prompting and evaluation question more than a code one, a good
  candidate for the eval harness in §11 to actually track, rather than
  something to "fix" once. **(needs Opus)**: it needs a real model.
  **Next:** a case set in `tests/eval/` (time-sensitive questions that should call `web_search`, stable ones that should not) scored by `pytest -m evals` after `scratchpad/llama-dev.sh serve`; WORLD_CLASS_PLAN B5 owns the harness.

**Privacy and security, specific to search**, extending §8b's general
security pass with what's particular to this feature. What's already true:
only the search words leave the machine, never notes; the request looks like
an ordinary browser rather than naming the app; no cookies survive between
searches; queries go by POST so they don't land in access logs; tracking
parameters are stripped from result URLs before they're ever shown; a
self-hosted SearXNG keeps the query on the user's own network entirely
rather than reaching a third party at all. Worth checking on top of that,
now that SearXNG is a real running thing rather than a plan:

- ~~**SearXNG's own outbound behaviour.**~~ **Built, see `search/searxng_settings.py:113-151` (autocomplete off, image proxy on, the outgoing section and the plugin list written explicitly, with a test in `tests/test_searxng_install.py`).** A default SearXNG install can be
  configured to query dozens of upstream engines, including ones with their
  own tracking, and some engine plugins hit third-party autocomplete/suggestion
  endpoints unless turned off, the `tracker_url_remover` plugin was already
  found to break startup entirely (§8b, bug 5) and disabled; worth a pass
  over the *rest* of the generated `settings.yml` for anything else
  defaulting to "on" that shouldn't be, not just the one that crashed.
- ~~**SearXNG bound to localhost, not the LAN.**~~ **confirmed for the
  source path, and it was wrong for docker**, `_start_docker` published on
  every interface (docker's own default), which is worse than an open port
  since SearXNG has no auth in front of it. Fixed; see HISTORY.md.
- ~~**A visible statement of what's true**~~ **Built 2026-10-05, see `frontend/index.html` `#websearch-help` and `tests/test_websearch_privacy_copy.py`.** Not just true in the code. The
  Privacy and security section of the README already says most of this
  clearly; worth linking it from Settings → Web search directly, next to the
  engine picker, so the privacy properties are legible exactly where someone
  is deciding whether to turn search on, rather than something you have to
  already know to go and read. **(needs Opus)**: copy and a '?' in Settings, Web search.
  **Built-now, 2026-10-05:** the `websearch-help` '?' popover (`frontend/index.html`, Settings, Web search) now states the properties in the code (search words only, a browser-like request, no cookies kept, POST not GET, tracking parameters stripped, a self-hosted engine staying on your network).

---

## 14. More tools worth adding

Pickup notes (2026-10-05, read before building; deferred until after PR 162):
- The six named tools are still missing. Check the registry's real count first: the README says 65, while this section said 58.
- `execute_tool` already files writes as `ai:<tool>` through `events.acting_as` (`ai/tools/__init__.py`), so a new tool only needs a test for it.
- Undo is a single tool call posted back to `/chat/tools/execute` (`chat-agent.js`, `changeRow`). Its arguments may carry extra keys, which `move_notes` needs in order to put each note back in its old category.
- `move_notes` to a space can reuse `routes_spaces.py`'s `move_notes_to_space`, once that body is lifted into a shared helper. `export_notes` writes into `_exports_dir()` (`routes_files.py`).
- There is no calendar events table: `core/events.py` is the change log, and the timeline's kinds are note, board, document and reminder. The plan for `add_event`: a `Reminder` row with a new `kind` column, which needs one migration. The plan for `list_events`: read the timeline over a date window.
- **Tried 2026-10-11 and deferred: L, not M.** Built and green: `Reminder.kind` (default `reminder`), migration `a1c5e8f2d7b3` after `d9b4e1a7c3f2` (guarded against the auto-migrator like `e6f2a9c4b1d7`, with its test), `add_event`, `list_events` and `delete_event` (the undo), `list_reminders` leaving events out, cards entries. `tests/test_manual_parity.py` then fails, correctly: a person has no way to make an event by hand, so the tool needs a kind control on the Reminders form (`shell-reminders.js` `addReminder`, `ReminderCreate.kind`), events drawn on the timeline and the Reminders list, and Help and Guide lines. Build the UI first, then the tools; the three tool bodies are small.

**Checked against the registry 2026-10-04.** Built since this list was
written: `create_document`, `related_notes`, `find_similar_notes`,
`notebook_overview` and `count_notes` (the stats), `save_user_preference`
(the allowlisted setting), `unlink_notes`, and `create_category`,
`rename_category`, `merge_categories` and `delete_category` (name-based, not
id-based, since the model has never seen an id; see HISTORY.md for the three
decisions behind the shape). **Still absent: `edit_document`, `move_notes`
(bulk re-file), `merge_notes`, `export_notes`, `add_event` / `list_events`
(§10) and `delete_reminder` (§21, the undo for a reminder change).
(needs Opus)**: each new tool moves the README's tool count, the help topics
and the schema budget together, and `merge_notes` and `edit_document` are
destructive, so each wants its own confirm design.
**Next:** checked 2026-10-05, the registry is 58 tools and none of these six exists. `merge_notes` and `move_notes` are WORLD_CLASS_PLAN B5's "pre/post conditions" example (both ids live; the category exists), so they belong to the harness agent; `add_event`/`list_events` need the `events` table (section 10); `delete_reminder` is two schemas and the Undo for `set_reminder` (`ai/tools/__init__.py:1556`). Each one moves `tests/test_readme_freshness.py`'s tool count.

> ~~**⚠ The prompt budget is now the binding constraint on this section.**~~
> **Lifted: the constraint was an assumption, not a fact.** `tools.
> within_budget` now fits schemas to the window the model *reports*
> (`ollama_client.usable_context`) rather than a fixed 4096, dropping the
> least-relevant tools when they don't fit and logging what it held back.
> Core tools (search, read a note) always go first. See HISTORY.md for the
> per-window table. **What this means for the rest of this section: add the
> tools**: the cost of one more is a per-turn question the app now answers
> itself, not a fixed budget to ration against.

---

## 15. Appearance: more of everything

Asked for: "more options for the appearances, fonts, colours, sizing, themes,
palettes."

- **Fonts** (`#font-seg` offers System, Serif, Mono, Arial; **Next:** a dyslexia-friendly face must be vendored under `frontend/vendor/fonts/` with its licence (an SIL OFL font is AGPL-compatible), an `@font-face` in `frontend/css`, a `data-font` value in `index.html:9368` and `settings-controls.js`, and per-surface choice is a second `--font-*` token pair in `00-tokens-shell.css`): beyond system/serif/mono: a curated set including a dyslexia-
  friendly face, plus per-surface choice (UI vs note body vs code)
- **Sizing** (UI zoom `#zoom-slider` and Text size exist; **Next:** line-height and measure are two new tokens read by `.entry-content` and the document reader, as a two-row Settings group in `index.html:9355` with a '?'): independent UI scale and reading size; line-height and measure
  (line width) controls, which matter more for long notes than font size
- **Colours** (accent swatches and a custom accent exist; **Next:** per-surface accents, a palette builder and a JSON import/export of a palette are not built, `settings.js` `LOOK_KEYS` is the list a saved look already captures, so export is `JSON.stringify` of it): per-surface accents, a custom palette builder (pick a base,
  derive the set), and import/export of a palette as JSON
- **More themes and palettes** (`#palette-grid`; **Next:** a "surprise me" is a seeded pick of accent, palette and density from the existing sets, applied through `applySavedTheme` in `settings.js`), and a "surprise me" that generates a coherent
  one
- ~~**Save a custom combination as your own theme**, not just a custom palette.~~ **Built, see `frontend/js/settings.js:1786` (`MAX_CUSTOM_THEMES`, saved looks, `applySavedTheme`).**
  Asked as "allow for saving of custom appearances and themes", the palette
  builder above already covers colour; a theme is colour *plus* light/dark,
  font, density, radius and glass (see "Themes vs palettes?" in the closing
  Q&A), so saving one as a named preset means capturing all of
  `appearancePref`, not just the swatches.
- **Live preview** while hovering a theme, before committing. **Next:** `applySavedTheme` writes through `appearancePref`; a hover preview needs the same writes held in a scratch layer and reverted on `mouseleave`, with the hover disabled on touch; `settings.js:1933` is the tile.
- ~~Fix the reported bug where individual controls resist change under a
  theme~~ done (§8, HISTORY.md).

---

## 16. Sweeping UI quality-of-life

- ~~**A status bar along the bottom**~~ **done** (`#status-bar`/
  `renderStatusBar()`), flagged stale by a backlog audit; see the
  near-duplicate bullet further down this list too.
- ~~**Sorting and grouping saved chats**~~ **Built (sorting), see `frontend/js/sheets-selects.js:1478` (`sortConversations`: Recent, Most turns, Most tokens, A-Z, with the pinned chats first) and `#chat-sidebar-sort` (`index.html:2171`); grouping by model or folder is not built.** Also from IDEAS.md and also homeless
  until now. Conversations sort by recency and nothing else; there is no "by
  length", "by which model answered", no folders, no grouping by topic. The
  data to sort by is already stored per turn (the model, the token cost, the
  timestamps), so this is a list-rendering job. The IDEAS note suggests an
  agent tool and a skill for it too, which would fall out of §14's shape once
  the sort exists. **(needs Opus)**: which sorts and groupings, a list design.
- ~~**Undo toasts** for anything soft-deleted, instead of confirm dialogs~~ **Built, see `frontend/js/status.js:1190` (`pushUndo`, the undo bar and the toast's Undo).**
- ~~**Optimistic UI**: a saved note appears instantly and reconciles~~ **Built where it matters, see `frontend/js/library.js:7404`, `7642` and `7801` (optimistic, corrected when the server refuses) and the draft that survives a failed save (`app.js:229`).**
- ~~**Consistent empty states** and loading skeletons~~ **Built, see `docs/DESIGN.md:527` (`.empty-state`) and `:543` (`showSkeletons`/`clearSkeletons`, swept by `f2-skel.js`).**
- ~~**Keyboard**~~ **Built, see `frontend/js/settings-wiring.js:915` (`/` jumps to search), `:1068` (`TAB_JUMP_KEYS`, `m` then a letter) and `activeOverlay()` (Escape and the Tab trap on every `aria-modal` dialog).** `/` focuses search, `g`+letter jumps tabs, Escape closes every
  overlay
- ~~**Bulk selection** in the note list~~ **Built, see `frontend/js/skills.js:1241-1377` (the selection bar: move to a category, tags, more) and `tag-manager.js:674` (`openBulkTags`).**
- ~~**"What changed" after an AI action**~~ **Built, see `frontend/js/library.js:41` and `chat-agent.js` (`changeRow`, one row per write with View and Undo; the tool chip is a `<details>` with arguments and result).** Chips say what ran, not what it did
- ~~**Confirm on close** with unsaved text~~ **Built, see `frontend/js/navigation.js:1703` (one `beforeunload` guard) and `confirmLeavingUnsavedWork`.**
- ~~**Relative timestamps** everywhere, absolute on hover~~ **Built, see `frontend/js/note-cards.js:1945` (`relativeTime`) and about 35 other call sites across the tabs.**
- ~~**Dashboard**: audit every quick-access button actually lands where it
  says~~ done (§8): every quick link now checked from all three Notes
  sub-tabs. Still worth doing: **add the ones that are missing**
- ~~**Collapsible sidebars.**~~ **Done**: `makeSidebarResizable`'s
  `sidebar-collapse-toggle` is wired on all three (Notes, Chat, Documents).
- ~~**A status bar pinned to the bottom.**~~ **done, same item as above**,
  a second, near-duplicate bullet for the same ask; both are satisfied by the
  one `#status-bar` that now exists.
- **A global quick-capture hotkey in desktop mode.** Not asked for directly,
  but the app's own pitch, "just capture, a local AI files it", implies
  capture should be as close to zero-friction as opening the app currently
  isn't. `--desktop` (§7) already owns a native window; a system-wide
  hotkey that pops a capture box without switching to the app at all (the
  way Apple Notes' quick note or Notion's quick capture work) would make the
  core loop genuinely faster than opening a tab, typing, and filing,
  rather than just as fast. Browser-tab mode can't do this (no OS-level
  hotkey access from a page), so it's specifically a `--desktop` win, and
  worth scoping alongside the rest of §7's packaging work rather than
  separately. **(needs Opus)**: an OS-level hotkey in the desktop window,
  untestable in this sandbox.
  **Next:** pywebview has no global hotkey, so this needs a new Python dependency (a `keyboard`-style hook) and the tray's `_new_note` (`__main__.py:2046`) as the target; a new dependency is the owner's call (FIX_COMMON rule 2). The tray's "New note" already does the one-click half.
  **The owner, 2026-10-27, verbatim** (screenshots: the ChatGPT desktop pet, a small pixel creature at the screen corner over the taskbar, with a Settings / Hide Mini menu): "is it possible to have the companion be like a corner thing that can actually show on the user's main screen outside of the app if they dont have th ewindow open?? like the chatgpt pets and then if the user clicks it they there can be a window to quick add a note, quick searchm or to open the app window." Plan: a second pywebview window in `--desktop` mode (frameless, on top, transparent where the platform allows, else a small rounded card), shown while the main window is in the tray; it draws the chosen companion; a click opens Quick note, Quick search, Open Tessellate; right-click Settings, Hide. No new dependency (pywebview and the tray's `_new_note` exist). Needs the owner's go and a Windows check (untestable here).

---

## 17. Use cases the app can't serve yet

- ~~**Meeting notes**~~ **record → transcribe → note built (a
  `#meeting-overlay`, `/voice/transcribe-meeting`, review-before-save, a
  `meeting` tag); action-item extraction still open**, needs a real model
  call parsing free text into multiple structured reminders, a different
  shape from the single-phrase parser `POST /reminders/parse` does, and
  this sandbox has neither faster-whisper nor a running Ollama to verify a
  new prompt against. See HISTORY.md for what was and wasn't verified live.
  **Built since, in part:** `ai/librarian.py:1128` (`summarize_meeting`) extracts decisions and action items into a block on the saved note (section 106). **Next:** turning each action item into a reminder is `saveMeetingNote()` offering one `POST /reminders/parse` per item as a checklist the person ticks before saving; the parser already resolves "in 2 hours" by rule (section 22), so no new model call.
- ~~**Reading and research**~~ **Built, see `frontend/js/note-cards.js` (the "from the web" badge, `Entry.source_url`) and the selection menu's "Save with its source" (`selection.js`).** The Browse section (§3) plus highlights saved as
  notes back-linked to their source
- **Task management**: **Next:** a decision for the owner, not a build; checklists in notes already feed the Unfinished widget (`dashboard.js` `renderUnfinishedWidget`) and map topics carry tasks with roll-up (MINDMAP_PLAN decision 15). Reminders are not tasks (no sub-tasks, projects, or
  "someday"). Commit to it or stay deliberately out.
- **Study / revision**: **Next:** nothing exists (no flashcard or review code in `src/` or `frontend/js`, checked 2026-10-05); the seam is `Entry.access_count` plus the `ai/resurface.py` score table; one "Review" Library chip and a due-date column are the smallest shape, needs a design row first. Spaced repetition; access-count and embeddings are
  already stored
- ~~**Sharing one note or document**~~ **Built, see `api/routes_entries.py:2113` (`GET /entries/{id}/export.md`) and `routes_documents.py` (the document's own export), `core/docexport.py`.** No export-one-thing path today
- ~~**A second device**~~ **Built for the phone-on-the-same-network half, see `core/netbind.py` ("Allow other devices on this network", off by default, password-gated, `POST /auth/lan-access`).** **Pointer:** sync itself is WORLD_CLASS_PLAN B6 and H5 (design only; section 112.5 of this file says why it is deliberately not built). Single-user by design; sync is a much larger decision
  and should be stated as out of scope rather than left implied. Asked
  concretely as "a way to run the app on a mobile device like my iPhone",
  which is a smaller ask than sync: the frontend is already a PWA with a
  mobile pass (Wave F), so a phone on the same network *could* just point a
  browser at it: except the server binds to `localhost` on purpose (§1 of
  `ARCHITECTURE.md`), which is exactly what stops that. Opening it to the LAN
  is a real security decision (anyone on the network reaches an unlocked API
  surface until the password gate, not just the person at the keyboard), not
  a config flag to flip quietly, worth stating explicitly as "possible, not
  yet safe to default to" rather than leaving it unaddressed.
  - **If sync is ever actually pursued**, the shape worth reaching for is
    the one Gemini's (grounded) suggestion named: local-network only:
    mDNS discovery plus a direct connection between two instances on the
    same network, never a public relay, which keeps the "nothing leaves
    the machine unless asked" principle intact in spirit (nothing leaves
    *the network*) rather than quietly becoming a cloud feature. Recording
    the shape without changing the decision above: sync is still a much
    bigger undertaking than the mobile-access question alone, and worth
    staying out of scope until that's a deliberate yes.

---

## 18. Agent quality

The registry is now 28 tools and reaches the whole notebook, documents and chat
history. What's still weak:

- ~~No plan/progress for a multi-step job~~ **Built, see `make_plan` (`ai/tools/__init__.py`) and the ticked steps in the timeline (`chat-agent.js`).** The step timeline shows what happened,
  not what remains
- ~~No way to stop an agent turn mid-way and keep what it already did~~ **done**
  - `#chat-stop` aborts the stream and keeps the partial answer.
- ~~A tool that fails is reported, but the model isn't told how to recover~~ **Built, see `ai/agent.py:640` (`_RECOVERY_HINTS`, the `what_to_do` field).**
- ~~`_CLAIM_PATTERN` catches "I saved it" when no write tool ran~~ **Built, see `ai/agent.py:1203` (`unsupported_claims`, `_CLAIMED_ACTIONS` for linking, reminders and more, the passive voice at `_PASSIVE`, and `CLAIM_RETRY_NUDGE`).**
- **No fallback when the configured chat/agent endpoint errors.** Checked
  directly: `ai/ollama_client.py`, `ai/openai_client.py`, and `ai/provider.py`
  all talk to a single configured endpoint per role; a timeout or a 5xx ends
  the turn, nothing tries a second endpoint. Odysseus's
  `foreground_model_routing.py` is a shape worth taking as an idea: opt-in,
  per-user, an ordered list of up to ten fallback endpoints, tried only on a
  named allow-list of retryable statuses (408, 425, 429, 500, 502, 503, 504,
  507, 508, 529), never a silent catch-all. See ANALYSIS.md's "Odysseus read
  deeply, 2026-09-21" section, item 2, for the size/risk call (M, must stay
  strictly opt-in so a local request never silently reaches an endpoint the
  user did not explicitly add).
  **Next:** a `fallback_endpoints` preference (`core/config.py`), tried in `ai/provider.py` only for the listed statuses, with a Settings, Models list and its '?'; `tests/` seam test that a local request never reaches an unlisted endpoint. Provider code, so coordinate with the harness agent.
- **The agent controlling the screen itself**, "allow the agent to control
  your screen within the application to navigate and make changes… with the
  user able to cancel it at any time". A different and much bigger thing than
  the tool-calling loop that exists today: it means the agent driving the
  frontend the way the Playwright driver in §10 of `ARCHITECTURE.md` drives
  it for testing, not just calling an API. Flagging it rather than scoping
  it: it would need its own cancellation and audit story on top of
  everything §21 already built for tool calls, and it's worth deciding
  whether the tool registry can get there first before reaching for UI
  automation.
  **Next:** a decision for the owner (it needs its own cancellation and audit story); the `GET /chat/tools` and `POST /chat/tools/execute` registry (WORLD_CLASS_PLAN B8) is the cheaper route and is built.
- (Odysseus, fourth read 2026-10-10) 

---

## 19. Accessibility audit

Deserves one deliberate pass rather than more ad-hoc fixes. **Two of the five
are now done** (§85, §86):

- ~~Focus traps in overlays are inconsistent~~ **done.** `activeOverlay()` no
  longer works from a hard-coded list of eight ids, it finds any visible
  `[role="dialog"][aria-modal="true"]` and takes the topmost, so a new modal is
  trapped from the moment it exists. Gated on `aria-modal` specifically
  because 13 of the app's dialogs are anchored *popovers* whose page stays
  interactive, and trapping Tab in one of those would be a worse bug than the
  one being fixed.
- ~~Tap targets below the WCAG 2.5.8 24px minimum~~ **done**, and the original
  finding was half wrong: it named the checkbox elements, but a wrapping
  `<label>` makes the label the target. A live sweep of every tab and Settings
  found five real failures (a 1px-short chip, two label-wrapped toggles at
  20px, a bare 13×13 Library tick, and one Settings link) and fixed them.
- ~~**Colour contrast is still unverified against WCAG AA**~~ **Built, see `scratchpad/ui-sweeps/contrast.js` and `contrastui.js` (computed colours against computed backgrounds, light and dark; `scripts/gate.sh --sweeps` runs it) and HISTORY.md "Board cards failed WCAG AA over a light board".** For the newer
  palettes and the glass surfaces in particular. Never actually measured: the
  one item here that needs a tool rather than a reading.
- **A screen-reader pass**: **Pointer:** section 115 row 4 of this file (WCAG AA and an axe pass, gate `a11yname.js`, `contrast.js`, `touch.js`) and WORLD_CLASS_PLAN section 1.7. Several dynamic regions still announce nothing.
  `announce()`/`#live-region` exists and the graph uses it well; most of the
  app does not.
- ~~**`prefers-reduced-motion` fallbacks**~~ **Built, see `frontend/css/02-chat-graph.css` (the two blankets that zero every transition and animation) and `tests/test_motion_recipes.py` (`glide.js` measures it under `REDUCED=1`).** For the remaining meaningful
  animations. 15 blocks exist; nobody has audited what is *not* covered.
- ~~**Settings on a narrow viewport**~~ **Built, see HISTORY.md "The Settings modal at phone width" (single column at 390px, `#settings-btn` rules) and UI_MODERNISATION_PLAN Phase 11.** Folded in here rather than fixed in
  isolation, since it is likely the same class of breakpoint gap.

## 20. Backend

- **Async httpx client**: **Next:** section 78 says the sync routes are correct, so this is optional; measure first with `scratchpad/ui-sweeps/apibench.js`, then switch only `ai/ollama_client.py`'s streaming read (nothing in `src/` uses `httpx.AsyncClient`, checked 2026-10-05). Touches the streaming path, which is what makes chat
  feel responsive, so a subtle regression wouldn't show up in tests. Do it with
  §6.
  **Decided 2026-10-11 (data-1011): not built.** Section 78 stands (the sync routes are correct); the streaming read is the one path that would change, a regression there would not show in tests, and nothing measured asks for it.
- ~~**Alembic migrations**: the additive auto-migrator cannot rename or drop, and
  won't survive a real schema change~~ **Built.** `migrations/` (Alembic),
  `_ensure_alembic_baseline()` (`core/database.py`) stamps any pre-existing
  database at the baseline revision on first run under the new system so it
  never tries to replay history against data that already has the schema.
  Full narrative: HISTORY.md §100. Stale here since: found by checking the
  running app before trusting this list, not assumed.
- ~~**Session TTL**: tokens live in memory and never expire~~ **done.** Two
  clocks (idle 12h, absolute 7d), expiry closes the vault too. See
  HISTORY.md.
- ~~**Cross-origin requests against the local API, worth checking directly,
  not assuming.**~~ **checked, and it was open. Now closed** by
  `core/security.py:OriginCheckMiddleware`. The real exposure was worse than
  the item assumed: the most vulnerable moment is *before* a password
  exists, when a drive-by `POST /auth/setup` from a malicious page in
  another tab could have claimed the notebook outright, a browser enforces
  the target's CORS policy, not the attacker's. See HISTORY.md.
- ~~**Is SQLite in WAL mode?**~~ **yes, and it already was**,
  `core/database.py` sets it on every connect, `busy_timeout=5000` and
  `synchronous=NORMAL` beside it. Pinned by a test now.
- ~~**What blocks the request thread.**~~ **Checked directly, not assumed,
  none of the three named cases actually do.** A re-index
  (`model_manager.start_reindex`) and a model pull
  (`model_manager.start_pull`) each spawn a daemon `threading.Thread`
  before returning, same as `searxng_manager.start()`'s own install/start
  path: none of the three ties up the thread serving the request that
  triggered them. **The daily backup is different, and safer than the
  worry implied**: `_backup_if_due()` (api/app.py) runs once during
  `create_app()`, *before* uvicorn starts accepting connections at all, a
  due backup makes the app take longer to finish starting, not something
  a live request ever waits on mid-session. A manually-triggered backup
  (`POST /backups` → `backup.backup_now`, a plain sync route function) is
  the one real nuance: FastAPI runs a sync `def` route in its own bounded
  threadpool, not on the asyncio event-loop thread, so it doesn't freeze
  concurrent requests the way a truly blocking call on the event loop
  would: it just holds one worker-thread slot for the copy's duration,
  which is a non-issue for a single-user local app with nobody else
  concurrently hitting the API. Nothing here needed fixing; this item can
  be struck rather than built.
- ~~**Singletons and worker count are coupled, and that coupling isn't written
  down anywhere.**~~ **done: checked in the running code, not assumed.**
  `deps.refuse_multiple_workers()` already exists and already runs first
  thing in `create_app()`, before any singleton is built: it reads
  `--workers`/`-w` off `sys.argv` and the `WEB_CONCURRENCY` env var (what
  uvicorn and gunicorn both honour), and raises `MultipleWorkersError` with
  the full reason and the fix rather than a warning nobody reads. Covered by
  `tests/test_worker_guard.py`. This item can be struck rather than built.
- ~~**Confirmed, not just suspected: `GET /entries` is genuinely
  unbounded.**~~ **done.** Asked for directly ("that is a real app feature
  that enhances good design and will probably be needed for real world
  use"). `GET /entries` now takes `limit`/`offset` (default page 1000, hard
  ceiling 5000: `ENTRIES_PAGE_SIZE`/`_MAX` in `routes_entries.py`) and
  reports the true count via an `X-Total-Count` response header regardless
  of the page. `entry/manager.py` grew matching `limit`/`offset` params on
  all three list functions plus `count_entries`/`count_deleted_entries`/
  `count_archived_entries`, additive (`None` still means "everything"), so
  every existing in-process caller is unaffected.

  The risk this item itself named, a silent cap making old notes invisible
  everywhere at once: is why the fix isn't just a `.limit()`. `app.js`'s
  `loadEntries()` now fetches pages in a loop, painting the first page
  immediately and filling the rest in the background; every one of
  `allEntries`'s ~30 read sites (search-as-you-type, keyboard nav, the
  sidebar, tag suggestions) needed zero changes, because `allEntries` still
  ends up exactly as complete as it always was once loading finishes, just
  without one unbounded response getting it there. A `_entriesLoadGeneration`
  counter (same shape as `loadOnboardingDiagnostics`'s staleness guard)
  stops a slow page from a superseded load splicing stale rows back in if
  `loadEntries()` is called again mid-page-load.

  One real regression caught in the same pass, not by guessing but by
  grepping every `/entries` GET call site before calling this done: three
  dashboard widgets (`renderPinnedWidget`, `renderRecentNotesWidget`,
  `renderTopTagsWidget`) each independently re-fetched the *whole* list,
  which the new 1000-row default would have silently truncated,
  `renderTopTagsWidget` most seriously (wrong tag counts on any notebook
  past 1000 notes, with no error to notice it by). Fixed by having all
  three prefer the already-loaded `allEntries`, the same pattern
  `renderRandomNoteWidget` already used. Also found and removed while
  auditing those call sites: `copyLogs()` built a `/entries` URL and
  `fetch`ed it, then never used the response, dead code, unrelated to
  logs, silently wasting a request (and failing every time, since a bare
  `fetch()` skips the auth header `api()` adds).

  Verified live, not just by the new backend/frontend tests: seeded 2500
  notes directly via `entry.manager`, confirmed exactly three page requests
  fire (`limit=1000&offset=0/1000/2000`), `allEntries.length` and the
  status bar both land on 2500, all 2500 rows actually render, and the
  Dashboard's own widgets (including the fixed tag-counting one) show
  correct totals with zero console errors, screenshotted.
- ~~**What happens when Ollama hangs, rather than errors.**~~ **Checked
  directly: already built, all three pieces this item asked for.**
  `OllamaClient.__init__` (ai/ollama_client.py) sets a 600s request
  timeout by deliberate design, not the default, its own comment records
  the exact live report that set the number ("models larger than like 4B
  params struggle to even load or respond") and the reasoning: long enough
  to cover a slow cold load on CPU-only hardware, short enough to
  eventually give up rather than hang forever. The frontend's own
  "still waiting" half already exists too: `sendChatMessage`'s
  `slowLoadTimeout` (app.js) shows "Loading model… (this may take a
  moment)" once 5s have passed with no reply. And the failure past the
  timeout is surfaced, not silent, `routes_chat.py`'s streaming
  generator has an outer `except Exception` boundary around both "before
  the first event" and "mid-stream" that turns *any* unhandled error,
  including a `requests.ReadTimeout` once 600s is up, into a real answer
  event ("Something went wrong before it could start: …") instead of the
  stream just stopping. Nothing here needed building.
- **Crash-safe recovery for a re-index or a model download interrupted
  mid-way.** Half-checked directly. **The re-index half is safe by
  design, already, without a resume button**: `_run_reindex`
  (ai/model_manager.py) deletes an entry's stale vector and commits, *then*
  regenerates and stores the new one, so a crash between those two steps
  leaves that one entry with no vector at all, not a corrupt or
  inconsistent one, and `start_reindex`'s own docstring already covers this
  exact state: semantic search falls back to keyword search for any entry
  missing a current vector, the same fallback a re-index that hasn't run
  yet relies on. The in-memory `Job` doesn't survive a restart either, so
  there is no stale "still running" status to confuse the health-check
  screen: a fresh launch just sees no job, and the next re-index (full,
  not a true resume-from-checkpoint) fixes whatever was left incomplete.
  No corruption, no confusing error, nothing to build here. **The model-pull
  half is still genuinely open**, whether a `POST /api/pull` cut off
  mid-stream resumes from Ollama's own blob store on the next pull is
  Ollama's own behaviour, outside this codebase, and wasn't verified this
  session (no live Ollama in this sandbox to interrupt and re-pull
  against).
  **Next:** needs a real Ollama (`scratchpad/llama-dev.sh` serves llama.cpp, not Ollama): start a pull of a small model through `ai/model_manager.py` `start_pull`, kill the server mid-stream, pull again and read the first progress frame; the owner's machine, not the sandbox.

---

## 21. Skills: rebuilt; what is left

**Why.** Reported directly: "the skill system also needs a remake. The way
skills are used currently, and what the skills are at the moment, are
incorrect and are closer to just presaved mini prompts. I keep on trying to
get the AI to make me some skills in the chat but it doesn't recognise that it
needs to use tools and how to properly utilise the workspace."

**That description was accurate**, and the shape has changed. A skill was
`{name, prompt}`; clicking one dropped its prompt into the chat box, and
`save_skill` stored a name and a string, so "make me a skill that files my
inbox notes" could only produce another sentence, because the storage had
nowhere to put the steps. Fixing the prompt alone would not have helped.

**What a skill is now** (`ai/skills.py`, one validator for every way in):

- **prompt**: what it should do. A skill with only this behaves exactly as it
  did before, which is why nothing was lost.
- **steps**: ordered instructions, numbered into the run instruction and
  drawn as a plan at the top of the step timeline before anything runs.
- **tools**: an explicit allowlist. Only those schemas go on the wire and
  anything outside the list is refused at execution, so it is a safety
  property and not just a prompt. It is also §11a: the full registry is 10,215
  characters of schema on *every round*; "🏷 Auto-tag my notes" ships 1,963.
- **inputs**: declared `{{placeholders}}`, asked for before the run. A
  placeholder with no input behind it is refused on save, in the editor and in
  `save_skill` alike, because the alternative is a model handed a literal
  `{{tag}}` inventing a value.

Two decisions worth keeping:

**The built-in skills moved out of `app.js`** and are served from
`GET /skills` with the user's own. The server could not previously resolve a
skill the user clicked, `list_skills` answered "you have none" while ten were
on screen, and every field added to a skill had to be added twice.

**The declared tools are named in the instruction text as well as narrowed on
the wire.** Not redundancy: the reported failure was a model that *had* tools
and did not know it was meant to act, and telling a 3B model "use `tag_note`"
is what makes it reach for one.

**And what running one now does** (`ai/skill_runner.py`):

- **One turn per step.** Not one request carrying a numbered list, that is a
  plan the model may ignore, and a 3B model given four instructions at once
  does the first and narrates the rest. The app knows which step is running,
  so the UI ticks them off as they finish.
- **A step that fails is named**, with the reason, and the run stops there
  instead of ploughing on. §21 asked for exactly this.
- **The run ends in what changed**, not prose claiming something happened:
  a list of every write, each with a **View** and, where an inverse exists,
  an **Undo**. The undo is a tool call captured *before* the write and run
  through `POST /chat/tools/execute`, the same endpoint the confirm button
  uses. It is stripped out of what the model sees, since every field left in
  a tool result is resent on every later round.
- **Every built-in is a real job**: steps, tools, and declared inputs asked
  for in one dialog before the run. "Draft an email" asks who and what
  instead of spending a chat round on it.

**Still to do:**

- **Re-running a past run.** A skill is repeatable; a *run* is not yet
  something you can replay over a different set of notes. **(needs Opus)**
  **Next:** `ai/skill_runner.py` keeps the run's steps and inputs; a "Run again" on a finished run's header (`frontend/js/skills.js`) re-posts them with a changed note scope, no new table needed until the history is kept past the session.
- ~~**Undo the whole run**, rather than one change at a time.~~ **Built** (AGENT_SKILLS_REFORM: a skill run's own Undo, `undoSkillRun`, "Undo the run" in the chat's "What changed"; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)"). **Still open, (needs Opus):** the heavier version Gemini named, a silent snapshot taken before a bulk run and kept for a short window ("one more backup, triggered by an event instead of a timer", through the existing backup mechanism), the middle size between a daily backup and a per-change Undo.
- **Reminders have no inverse tool** (links do: `unlink_notes` exists, checked
  2026-10-04), so that change is
  listed without an Undo. `delete_reminder` would fix it, at
  the cost of two more schemas in the per-round budget (§11a): worth doing
  when something else needs it too. **(needs Opus)**: a new tool moves the
  README's tool count, the help topics and the schema budget together.
  **Next:** see section 14 (the same missing tool); `ai/tools/__init__.py:1556` `_set_reminder` is where its undo is captured.

---

## 22. Reported in use, not yet done

Small, concrete, each seen in the running app:

- ~~**Take me to the thing the agent just changed.**~~ **Done, this entry
  was stale.** Checked against the running app (agent.py), not assumed:
  `_change_note_id`/`_change_document_id`/`_change_reminder_id`/
  `_change_category_name` all exist and are wired into every `change` event
  (`create_note`, `edit_note`, `tag_note`, `pin_note`, `restore_note`,
  `link_notes`, `unlink_notes`, all four route through the note's own id,
  which is the right target for "View" either way; `create_document`;
  `set_reminder`/`complete_reminder`; `create_category`/`rename_category`/
  `merge_categories`). `changeRow` (`frontend/js/app.js`) renders the View
  button from whichever id is present, and is called from both the live
  per-turn tool-call rendering *and* a skill run's final "what changed"
  list: the "two things to decide" below were both resolved. Only the
  destructive-result question below is still open, and it's a small,
  separate decision, not a rebuild.

  ~~Still open: whether a **destructive** result... should offer to
  navigate to the recycle bin~~ **Done for notes, the only one of the three
  that was actually wired.** `changeRow`'s "View" button on a `delete_note`
  result reused `flashEntry`, which only ever looks in the ordinary browse
  list: a note just moved to the bin is never there, so it silently found
  nothing. `delete_note` now gets its own "View in bin" button
  (`flashLibraryItem`, `frontend/js/app.js`), which opens the Library's Bin
  filter and highlights the note there, the one place it actually lives.
  Verified live (Playwright): create → delete via the API → call the new
  function → lands on Library, Bin filter active, correct card found and
  highlighted, across three repeated runs. Document and category deletes
  never route through `changeRow`'s note-id branch at all (`delete_document`
  is parked for a confirm rather than reaching this code path, per
  `agent.py`'s own comment on `_DOCUMENT_ID_FIELD`; there's no
  `delete_category` change event either): so there was nothing else to fix
  under this item, not a partial fix.

- ~~**Magic Add schedules relative reminders a whole timezone offset late.**~~
  **fixed**: the route built the user's clock as `utcnow() + offset`
  (aware, tagged UTC, actually holding local wall-clock), so the model was
  told a fictional offset and trusted; error was exactly the user's UTC
  offset. Also: "in …" phrases now resolve by rule, not a 3B model doing
  arithmetic. See HISTORY.md.

- ~~**Background tasks vanish when they finish.**~~ **Done**,
  `renderTaskHistory` persists finished tasks (outcome, duration) and
  `task-history-clear` is the shared "clear history" affordance.
- **Agent continuation quality.** "The agent really struggles to continue a
  chat based off the previous message." Two things landed for it (2026-07:
  the most recent answer now reaches the next turn nearly whole,
  `librarian.history_messages` / LAST_ANSWER_CHARS: and every agent turn
  logs its prompt composition as memorymap.agent "prompt composition").
  Next step per §11a: read those logs from a real 3-turn chat, see whether
  notes or history dominates, and only then trim the variable half. **(needs Opus)**: it needs a real
  3-turn chat on a real model.
  **Next:** `scratchpad/llama-dev.sh serve`, three turns through the agent, read the "prompt composition" log lines (`ai/agent.py`) for which part dominates before trimming anything; real model only.
- ~~**A skill that writes skills.**~~ **Built**, "Build a skill" in
  `ai/skills.py`'s `BUILTIN_SKILLS`, same `ask_user`-driven interview shape
  as "Interview me about an idea": asks what the job should do, whether it
  touches notes (decides the tool allowlist), what should be an input, drafts
  the whole thing and confirms before calling `save_skill`, and checks
  `list_skills` first so a near-duplicate ask reuses rather than doubling up.
- **Appearance settings page (§15).** **Next:** the audit is the section 15 list above, checked 2026-10-05 (fonts, line-height, palette import and export, hover preview are the gaps; saved looks are built). Asked whether it can be improved;
  nobody has audited it against §15 yet. The chat empty-state emblem now
  animates (same motion switch as the ai-mark), which was the one concrete
  ask. **(needs Opus)**: auditing the page against §15 is a design pass.
- **Bot-walled sites in the reader.** Cloudflare-fronted wikis and Reddit
  403/challenge the reader on TLS fingerprint alone; no header can fix
  that. The reader now names the wall instead of dumping a status
  (websearch.fetch_readable), but actually reading such sites would take
  browser impersonation: decide deliberately whether that dependency is
  ever worth it before anyone "fixes" this again. **(needs owner)**
  **Next:** options are (a) keep the named wall, which is built, or (b) an optional extra that impersonates a browser's TLS handshake, off by default; (b) is a new Python dependency, so the owner decides (FIX_COMMON rule 2).
- ~~**Chat metadata disappears on a reload or app restart.**~~ **Done, this
  entry was stale.** Checked against the running app (`openConversation` in
  `frontend/js/app.js`), not assumed: `message.stats` is persisted and the
  function's own comment already says why, "Rebuild the metadata line...
  it was only ever built from the live stream... Turns saved before this
  stored no stats and correctly get no line, rather than a row of '?'s."
  Whoever fixed this didn't strike the entry here.
- ~~**Notes don't render markdown.**~~ **done**, but read how before
  extending it. `renderInlineMarkdown` handles bold/italic/`code`/strike
  *only* (block elements are deliberately excluded from the list, see
  HISTORY.md); the dashboard's own small note lists strip markers instead.
- ~~**A hero header on the dashboard.**~~ **done**, emblem and wordmark
  inside the greeting card, hidden below 720px.
- ~~**The chat box can't grow.**~~ **done**: a textarea that grows with the
  text now, was a single-line `<input>`.
- ~~**A long note fills the list.**~~ **done**, anything past
  `LONG_NOTE_CHARS` clamps with a fade and "Show more".
- ~~**SearXNG starts but never answers**, capture its output.~~ Done; the
  cause was us: see §8b.

---

## 23. Organisation: manual grouping and multi-category notes

**Why.** Two related asks: "manually group notes together (separate from
the main sorting)" and "a note should be able to have multiple categories".
Both point at the same gap, filing today is exactly one category per note
(`entries.category_id`, a single foreign key, chosen by the janitor or the
user) plus tags for everything else multi-valued.

**Next (checked 2026-10-05):** `Space` (`core/database.py:129`, `api/routes_spaces.py`) already partitions the whole notebook by workspace, and the tag manager and Manage categories panel are built; a many-to-many `collections` table (manual grouping) and an `entry_categories` join (multi-category) are not. Decide with the owner whether a tag already serves, then one Alembic revision, `entry/manager.py` and `routes_entries.py`; the janitor's centroid rule (section 8) is the open design question for multi-category.

**Worth checking before building either.** Tags already are a multi-label,
user- or AI-applied system (`entries.tags`, a JSON column, with `tag:work` as
a search operator). A genuine "multiple categories" ask might already be
served by tagging more, worth finding out what the category is doing for
the person that a tag isn't (a category has an embedding centroid the
janitor matches against; a tag doesn't) before adding a join table.

**If it's still wanted after that:**

- **Multi-category** is a schema change, `entries.category_id` becomes a
  join table (`entry_categories`), and the janitor's cheap match (§4 of
  `ARCHITECTURE.md`) needs a rule for what happens when a note matches two
  centroids well. An additive migration, but touches the one part of the
  filing pipeline every other feature assumes is single-valued (the sidebar
  count, the graph's category layer in §9, "all notes in category X" queries).
- **Manual grouping**, kept genuinely separate from categories/tags, is
  smaller: a `collections` table and a join table, with no AI involvement at
  all: the person decides what belongs together, the app doesn't guess.
  Closer to a saved filter (§2) built by hand than to a new kind of filing.

---

## 24. Dashboard: more widgets, and layout depth

**Why.** Asked for directly: "more dashboard widgets! maybe some pie
graphs??" The dashboard already has a rearrangeable layout (Phase 5) and a
widget set (streak, at-a-glance counts, AI digest, activity heatmap,
on-this-day, focus timer): this is more of the same shape, not a new system.

- ~~**A category/tag breakdown**~~ **Built as ranked bars, see `frontend/js/dashboard.js:2998` (`renderCategoriesWidget`), `renderTopTagsWidget` and `renderTagCloudWidget`; a pie is not drawn (bars read better at eight rows).** The pie chart asked for, over
  `count_notes`-shaped data that already exists for the agent tool of the
  same name (§7 of `ARCHITECTURE.md`).
- ~~**A writing-frequency chart**~~ **Built, see `frontend/js/dashboard.js` `renderPaceWidget` ("Writing pace", words per day this fortnight) beside `renderHeatmapWidget`.** Bars over the activity heatmap's own data,
  a different read of the same numbers (streak vs volume).
- ~~**A "stale notes" widget**~~ **Built, see `frontend/js/dashboard.js` `renderRandomNoteWidget` ("Rediscover": old, unlinked and unopened, with the reason) and `renderOrphanNotesWidget` ("Loose ends").** Pairs with §10A's still-open idea of nudging on
  a note whose relative-time phrase has gone stale ("this said 'tomorrow'
  three weeks ago").
- **A "forgotten connections" widget: proactive rather than on-demand.** **Pointer:** WORLD_CLASS_PLAN I1 "The night shift" (its findings are what the "While you were away" widget, `renderNightWidget`, shows; `ai/facts.py` `KINDS` has claim, question, tension and answered but no connection kind yet).
  Gemini's actually-grounded suggestion (its second pass, after reading the
  real feature set): the graph already lets the AI suggest connections for
  a note *you're looking at* (§9); this is the same underlying similarity
  search run the other way, periodically, in the background, over notes
  nobody has looked at together, surfacing "these two from months apart
  might be related" on the dashboard rather than waiting to be asked.
  Nothing new to build on the retrieval side, §9's clustering and the
  embedding search both already exist; what's new is running it
  unprompted and having somewhere to show the result. Worth capping
  aggressively (one suggestion, not a feed) so it reads as a genuine find
  rather than the AI narrating its own similarity scores at you.
- Before adding more: audit which existing widgets render markdown and which
  don't (§8's ideas-parking-lot bug) so a new widget doesn't repeat the gap.

---

## 25. App control: tray, health checks, and dependency repair

**The tray itself: built.** Asked directly: "hide the terminal but let it be
reached", "manage it through the system tray and popup windows", and
answered: closing the desktop window now minimizes to a tray icon instead of
quitting (`window.events.closing` returns `False` to cancel the real close),
and the tray menu is Open / View Logs (opens Settings → Logs, the third
AskUserQuestion answer this session) / Restart (`os.execv`, same process
re-launched rather than a second one spawned) / Quit (`window.destroy()`,
which is what actually unblocks the `webview.start()` call and lets the
process exit). See `tessellate.__main__._start_tray`. `pystray` + `Pillow`
ride along with the existing `desktop` extra in `core/extras.py`, same
button that already installs `pywebview`, and the Windows installer's
PyInstaller spec bundles both, so this is always on for anyone who used the
installer.

Degrades the same way every other optional extra in this app does: no
`pystray`/`Pillow` (or, seen for real in this sandbox, a `pystray` backend
that fails at import, `Xlib.error.DisplayNameError` on Linux with no X
server) means `_start_tray` returns `None`, logs why, and the window goes
back to closing for real. That fallback path is what's actually been run in
this sandbox; the tray *appearing*, the menu *working*, and minimize-to-tray
*behaving* on a real Windows taskbar have not, no Windows box and no GUI
toolkit here to run pywebview at all, so this carries the same "built,
reasoned through, not yet seen" caveat §7's installer already carries, for
the same reason.

The health-check screen and repair actions below are still open, this
covers only the tray/console half of the section's original ask.

**Why.** Several asks that are really one request in different words: "an
interface for managing the application… backend, cmd prompt console, quit,
update, install/fix/uninstall/reinstall packages and dependencies,
faster-whisper, and more… application health check, errors", plus "improve
or expand on start.bat, don't make a cmd prompt window show but make it
accessible (maybe system tray)" and "a way to exit the app and close the
program quitting the backend". §7's desktop-packaging plan already lists
"single instance, native menus, tray" as part of hardening `--desktop`; this
section is the *content* of that tray/console, not the packaging shell
around it.

- **A visible health check.** **Partly built:** Settings, About, Health (`frontend/js/settings.js:433` `renderHealthBlock`, `GET /debug/health`) shows database size, counts, running jobs, last error and latency, and the onboarding "Your setup" slide checks Ollama and the data folder. **Next:** the missing rows are a verdict line each for the model, the embedding backend, SearXNG and free disk (`/models/status`, `searxng_manager.status()`, `/storage` `free_bytes` already answer them), in the same group. Is the venv intact, does Ollama answer, is the
  embedding model loaded, is SearXNG (if installed) alive, how much disk is
  `data/` using. Most of these already have an answer somewhere in the app
  (`/models/status`, `searxng_manager.status()`); this is one screen that
  asks all of them and states plainly what's wrong rather than making the
  person go looking.
- **Repair actions from that screen**, not just a diagnosis: **Next:** SearXNG Reinstall and Settings, Models' pull exist; the buttons to add beside each health verdict (above) are "Start SearXNG", "Pull the model again" and "Re-index" (`ai/model_manager.py` `start_pull`, `start_reindex`). Reinstall a
  dependency, re-pull a stuck model download, restart SearXNG. The SearXNG
  ↻ Reinstall button (§8) is the existing pattern to extend, not a new idea.
- ~~**A real quit**, distinct from closing the browser tab~~ **Built, see `api/routes_tasks.py` (`POST /shutdown`) and `core/quit_hook.py` (the desktop launcher registers the same close the tray's Quit uses).** Stopping the
  server process, not just the window. `--desktop` mode is the natural home
  for this since it already owns a process to exit; browser-tab mode can't
  kill its own server from the tab.
- **Update channels** (stable/beta/dev): **Next:** the installers ship now (`release.yml`), so this is unblocked; `api/routes_update.py` compares against `releases/latest`, a channel is a preference choosing `latest` or the newest prerelease. Owner's call whether beta exists. Worth deferring until §7 actually
  ships an installer; there's nothing to channel yet while `git pull` plus
  the launcher's own dependency check is the update path.
- ~~**A hidden console window on Windows, reachable rather than gone**~~ **Built, see HISTORY.md "Dev view / User view console mode" (`__main__.py` relaunches under `pythonw.exe` for User view; Settings, Logs and the tray reach the console).** The
  ask was for the cmd window not to show at all *and* to still be reachable,
  which is two different things depending on whether the point is "get it out
  of my way" (a tray icon, minimised) or "I don't need to see it, ever, but
  Settings → Logs already covers that" (nothing to build). Worth confirming
  which was meant.

---

## 26. Data lifecycle: archive, a full wipe, and a real trust page

**Why.** Groups a few related asks that are all "what happens to old or
unwanted data" rather than day-to-day filing: "data and note compression",
plus the general expectation that a local-first app should let someone see
and delete everything it holds, the outside review's "local data map,
retention policy UI" specifically, which is real and not yet one coherent
thing anywhere in the app.

- **Archive**: already scoped in §4 item 2 (an `archived_at` column,
  additive migration). This section doesn't repeat it, just notes it's the
  prerequisite for the rest here.
- **A "delete everything" control.** Export (JSON/CSV/Markdown) already
  exists; there's no equivalent single action for the other direction, wipe
  the database, uploads and preferences and start over, distinct from
  `--reset-password` which only clears the credential. Worth being as
  explicit about what it destroys as `--reset-password` already is.
  **(needs owner)**: a destructive control; the owner decides whether it
  exists and where it sits.
  **Next:** a `DELETE /notebook` in `api/routes_backups.py` that needs the password and a typed word, stops background jobs, closes the vault and removes the database, uploads and preferences, with a Settings, Data danger row and its '?'; the test runs it in a scratch data dir, never `cwd=ROOT` (CLAUDE.md section 5).
- **A real storage breakdown, not just the database file.** Asked for
  directly: "can the user see a visual depiction of the storage size the
  application takes up... so they can manage and uninstall optional
  dependencies they don't really use." `GET /storage` today reports only
  `database_bytes`, nothing for `uploads/` (attachments, sketches),
  nothing for the installed extras themselves (`core/extras.py`, which
  already has a real install/uninstall path but no size next to the
  button: `sentence-transformers` alone is the "~2 GB, it pulls in
  PyTorch" case named in its own catalogue entry, exactly the kind of
  thing worth seeing before deciding to keep it). Not a quick add: needs a
  directory-walk per extra's actual installed footprint (import metadata
  doesn't give you bytes on disk), likely cached rather than computed on
  every Settings load. The "uninstall now, reinstall later" half already
  works (`core/extras.py`'s remove/start): this is purely the missing
  "how much is this costing me" number and a chart on top of facts that
  mostly already exist. **(needs Opus)**: checked 2026-10-04, `GET /storage`
  still returns only `database_bytes`; the walk, the cache and the Settings
  line with its '?' are one design.
  **Built 2026-10-11 (data-1011).** `GET /storage` reports `uploads_bytes`, `media_bytes`, `backups_bytes` and `extras_bytes` (`extras.installed_bytes`, the installed extras' own files); each extra's `disk_bytes` already sat beside its Remove button; Settings, About, Health draws Files on disk as one bar and a legend (DESIGN.md recipe `.storage-bar`, `scratchpad/ui-sweeps/storagebar.js`).
- **One actual "your data" page, not the pieces scattered.** **Partly built:** Settings, Privacy, "Where your data went" (`frontend/index.html:11095`, `core/egress.py`) is the receipt. **Next:** a head line stating what is stored and where, with links to Export and the wipe above once it exists. The individual
  facts already exist: where the data lives and how big it is (README),
  what's in the audit log (Settings → Activity), what export and wipe do
  (above): but there's nowhere that shows all of it as one trust surface.
  This is mostly assembly, not new data: a page that states plainly what's
  stored, where, for how long by default, and links straight to export and
  wipe from the same screen, rather than requiring someone to already know
  those live in three different places.
- **Opt-in retention rules: "forgetting," not just "archiving."** Archive
  above is a manual action; nothing today acts on a note's age on its own.
  A genuinely opt-in rule ("auto-archive notes untouched for a year") is a
  different, smaller thing than automatic deletion, reversible, off by
  default, and closer to the "stale notes" dashboard nudge (§24) than to a
  destructive background job. Worth being conservative here: the app's own
  design principle is that saving a note never fails and nothing is lost
  silently, so any auto-archival needs to be loud about what it did, not
  quiet. **(needs owner)**
  **Next:** the owner decides whether it exists; the shape is an `auto_archive_days` preference read by `ai/autonomous.py`'s pass (`_optimization_pass`), which writes `archived_at` (built, section 4) and an audit row per run, with a dry run first and a bulk restore, the posture `core/media_gc.py` already takes.
- **Note compression**: asked for directly, and worth being honest about the
  payoff before building it. Notes are short text in SQLite; a notebook of a
  few thousand notes is low tens of megabytes uncompressed, and SQLite pages
  already compress well under most filesystems' own compression. This is
  likely solving a problem that doesn't exist yet at any realistic notebook
  size: worth measuring an actual `data/memorymap.db` before writing any
  compression code, not assuming it's needed. **(needs owner)**: see 79b.
  **Measured and decided 2026-10-11 (data-1011): not built.** A 2,000-note notebook is a 4.2 MB file; the notes table is 426 KB of it (10%), the audit log and its indexes 1.2 MB (30%), the search index 0.6 MB. Compressing note text saves a tenth at most, and the log is already compacted (`events.compact`). Revisit only when a real notebook shows note text above 40% of the file.
- **A synthesised export, not just a raw one.** **Skill built 2026-10-05** (HISTORY.md, "backlog-1005"): "Write a document from a tag" in `ai/skills.py`; the button on a graph or list selection is still open (it needs a place in the selection bar, a design call). Same item as sections 102 item 10 and 109.3 item 5. Export today (JSON/CSV/MD)
  is a dump of what's selected; Gemini's grounded suggestion was a step
  beyond that: pick a tag or a cluster and have the AI *compile* it into
  one coherent document (a project writeup, a portfolio piece, a README)
  rather than a folder of separate files the person still has to assemble
  by hand. Closer to a skill (§21) than to the export routes: it's a
  read-many, write-one operation with a prompt behind it, not a format
  conversion. Worth scoping as a skill once the skill system's tool
  allowlist (§21) is solid, rather than as a fourth export format. **(needs Opus)**

---

## 27. Onboarding and first-run experience

**Why.** Asked for directly: "a guided setup on first install (like setting
your name, choosing a model if one isn't yet downloaded, a tour, making the
first note etc)". There already is an `onboarding-overlay` (referenced by
every Playwright driver script in this document as something to dismiss
before testing), so this is about what it covers, not whether it exists.

- ~~**Confirm what the current onboarding actually walks through**~~ **done,
  five static slides** (welcome, capture, ask, graph, appearance), no
  diagnostics anywhere.
- ~~**Fold in first-run diagnostics.**~~ **built, Ollama reachability and
  where the notebook lives**, a new dynamic slide reusing the existing
  `/models/status`/`/storage` endpoints. See HISTORY.md.
- ~~**Name, first note, model choice**~~ **Built, see `frontend/js/onboarding.js` ("Your setup": the one-click model pull and example notes), `dashboard.js:509` (`dash-name-nudge`) and the guided tour (`tour.js`); a tour that ends in the person's own first note is section 115 row 6.** As asked, still open. (The one-click
  offer to pull a model and the data-folder writability line are built:
  `renderOnboardingActions` and `data_dir_writable`, checked 2026-10-04.) The dashboard's
  name-nudge work already solved the *name* half; onboarding doing it once
  at the start would be the same fix moved earlier, not a new one.
- ~~**Say what the graph and timeline actually are, once, early.**~~ **built**
  - the "Explore your graph" slide now names both the Graph tab and the
  Timeline's Line view.
- ~~**What stays local, and how much space it's using**~~ **built as part of
  the diagnostics slide above** rather than a separate step.
- **Benchmark installed models on first run, to suggest a default rather** **Pointer:** WORLD_CLASS_PLAN I8 "The model bench" (H3); this waits on `ai/bench.py`. (original wording follows:)
  than assuming one**: still open, blocked on §11's model-comparison
  feature existing to wire into, as originally scoped.

---

## 28. In-app help: an AI that knows the docs, built

Built as `ai/help_chat.py` and the Guide; the detail is in HISTORY.md. Kept for its number.

---

## 29. Extensibility ideas, not yet scoped

Three asks that are genuinely bigger than anything else in this document and
don't have a shape yet, recorded so they aren't lost, not because any of
them are close to being built:

- **MCP tool support**: **Pointer:** WORLD_CLASS_PLAN B8 "Extensions" and PLAN.md harness row A7 ("MCP in and out"); the consume half waits on the trust model. "an in-built browser with MCP tool abilities to
  accompany the web search". The Model Context Protocol would let Tessellate
  either expose its own tools (§7 of `ARCHITECTURE.md`'s 58-tool registry) to
  other MCP clients, or consume external MCP servers as more tools for its
  own agent. Either direction is a real integration, not a checkbox, it
  would need its own trust model, since an external MCP server is exactly
  the kind of thing design principle 1 (offline-first, one narrow opt-in
  exception for web search) currently doesn't have a category for.
  **No longer a blank slate**, ANALYSIS.md §60 (ROADMAP.md item 38) read
  odysseus's actual MCP implementation and split this into two: expose (no
  new trust model needed, build first) and consume (needs the trust model
  this paragraph already flagged, build second). **The expose half is built**
  (`src/tessellate/mcp_server.py`, a stdio server over the tool registry,
  checked 2026-10-04); consuming external servers is still open **(needs
  owner)**: it needs the trust model decided first.
- **A VS Code extension.** **Next:** nothing is buildable until the owner states a purpose; the HTTP tool API (`GET /chat/tools`, `POST /chat/tools/execute`, WORLD_CLASS_PLAN B8) is the surface an extension would call. No stated purpose yet beyond the idea itself,
  worth asking what it would let someone do that the app's own web UI, PWA
  and desktop window don't, before scoping anything. **(needs owner)**
- ~~**A browser clipper.**~~ **Built 2026-10-05** (WORLD_CLASS_PLAN row 24, D9): `POST /links/clip-page` (`routes_webclip.py`), the "Clip to MemoryMap" bookmarklet and `frontend/clip.html` / `clip.js`, `tests/test_webclip_page.py`. A packaged browser extension is not built; the bookmarklet is the capture path (HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)").
- (Odysseus, fourth read 2026-10-10) 

## 29c. Whiteboard, brainstormed: not yet triaged

Asked for directly (make the whiteboard "the best fusion of Microsoft
Whiteboard, OneNote, Draw.io, and Mermaid.js"), after ROADMAP item 11/25's
own confirmed list was cleared (HISTORY.md §56–§57). None of this is
scoped or decided: recorded so it isn't lost, same reasoning as §29
above, and specifically so it doesn't get rebuilt from scratch by a
session that only reads ROADMAP.md's live list.

**Triaged 2026-10-05:** each idea below now points at the row that owns it.

- ~~**Mermaid.js text-to-diagram, both directions.**~~ **Built:** a board's Mermaid out and in (`wbBoardToMermaid`, `wbMermaidParse`, `wbMermaidLayout`, `whiteboard-interchange.js`; `tests/test_wb_interchange.py`) and the document half (`mermaidFlowParse`, `tests/test_doc_mermaid.py`); HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)".
- ~~**Frames**~~ **built** (WHITEBOARD_PLAN decisions 14 and 18, a titled region that carries what is in it; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)"). **Swimlanes stay open** (`scratchpad/audit1005/features.md` section 4 row C6, P2; the object library has a timeline lane template only).
- ~~**Board templates.**~~ **Built** (BACKLOG 4b; the object library's `template` kind with a whole board saved to "Yours"; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)").
- ~~**A layers panel.**~~ **Built, phase 1:** the sidebar's Layers tab, the board as a tree in paint order (`wbRenderLayers`, `#wb-layers-tree`; WHITEBOARD_PLAN decision 27; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)"). Named layers (draw.io's) stay open as phase 2.
- ~~**Smart alignment guides while dragging**~~ **Done, see HISTORY.md
  §58** (edge/centre/spacing, colour-coded, Alt bypass).
- **Ink-to-text (handwriting OCR) on sketches.** **Decided out:** `scratchpad/audit1005/features.md` section 4 row C5 (no on-device ML, the no-torch rule; spec D3).
- ~~**Presentation/step-through mode.**~~ **Built** (WHITEBOARD_PLAN decision 16, `wbPresentSteps` steps through the frames; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)").
- ~~**A board version history**, separate from the undo stack.~~ **Built:** the board's time machine (`whiteboard-history.js`, `routes_board_history.py`, WHITEBOARD_PLAN decision 33; `tests/test_board_history.py`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)").

## 29d. Whiteboard: scoped and next, not brainstormed

Unlike §29c above, these four were specific asks from the same session
(HISTORY.md §58) with a clear shape. Three are now built (HISTORY.md §61);
the fourth, links to objects, is built too (checked 2026-10-05, below).

- ~~**Rename a board.**~~ **Done (HISTORY.md §61).** `PUT
  /whiteboard/boards/{id}` rewrites the underlying note's first `#
  heading` line; the one board that isn't a note (`board_id=None`,
  "Default board") is refused with a clear error rather than crashing.
- ~~**A Library gallery of boards, mind-maps, and uploaded images.**~~
  **Done (HISTORY.md §61).** The Library's whiteboard area is now two
  sub-tabs: "Whiteboards" (a board gallery over `GET /whiteboard/boards`,
  plus "+ New board", replacing the bare board-switcher dropdown as the
  only way to see what boards exist) and "Image Gallery" (sourced from the
  new `/media` listing rather than `/whiteboard/images`, since it also
  needed to cover plain note-image uploads, not just whiteboard image
  objects: see the Tier 3 media item in ROADMAP.md for what's still open
  there).
- ~~**A structured, small-model-friendly diagram-generation tool.**~~
  **Done (HISTORY.md §61).** `generate_diagram` takes a flat node list
  (`title` or `note_id`, plus `parent_ref`) and a `layout`
  (`tree`/`radial`), creates every card and link server-side in one call,
  and computes placement itself, a BFS depth/slot layout in Python
  (`_diagram_tree_positions`) rather than a full port of
  `wbArrangeMindMap`, since the AI tool only needed the placement math, not
  the interactive drag machinery around it. Capped at 60 nodes; refuses no
  root, more than one root/a cycle, an unresolvable `parent_ref`, and a
  node with both `title` and `note_id`.
- ~~**Links that can reach an object (image/text box), not just a card.**~~ **Built, see `frontend/js/whiteboard.js:2325` (a link stores `sourceKind`/`targetKind`, "node" by default), `api/routes_whiteboard.py:2931` and `ai/tools/whiteboard.py` (`add_whiteboard_link` takes the kinds).** Asked about directly (HISTORY.md §58): the border/anchor math itself
  Asked about directly (HISTORY.md §58): the border/anchor math itself
  (`wbAnchorPoint`/`wbLinkEndpoints`/`wbBoxRayIntersection`) is generic:
  it already takes a `kind`, and `wbItemBBox("object", ...)` already
  works: but every actual entry point to "what can a link end on" is
  hardcoded to cards only:
  - `dragEndNode`'s own hit-test (app.js) loops `for (const node of
    wbState.nodes)`, an object is never even considered as a drop target
    for the live drag-to-link gesture.
  - `add_whiteboard_link` (`src/tessellate/ai/tools/__init__.py`) does
    `session.get(WhiteboardNode, ...)` for both ends: passing an object's
    id raises "No whiteboard card with id …", not a working link.
  - The link sketch's own data shape (`sourceId`/`targetId`) has no
    `sourceKind`/`targetKind`, every render-time lookup
    (`sketchUpdate.each`, `wbUpdateLinkedSketches`) assumes both ends are
    nodes and would need a kind tag to know which state array to resolve
    an id against.
  Scoped shape: add `sourceKind`/`targetKind` (default `"node"` for every
  existing link, so this doesn't need a migration), extend the hit-tests
  above to also check `wbState.objects`, and give `add_whiteboard_link`
  optional `from_kind`/`to_kind` args. The board/self-link guards just
  added this session (`source.board_id != target.board_id`, `source.id ==
  target.id`) will need the same kind-awareness, comparing a node's id to
  an object's id is meaningless without also checking they're the same
  `kind`.

---

## 29e. Whiteboard master spec (uploaded, MS Whiteboard/OneNote/draw.io/
Illustrator feature audit): reconciled against 29c/29d, not transcribed

A large uploaded document (~790 lines) did an exhaustive feature-by-feature
comparison against four reference apps and proposed a 6-phase rebuild. Its
Part A (the reference-app feature catalogue) is solid and worth keeping for
future scoping. **Its Part B "current-state audit" and therefore Part C's
gap matrix are meaningfully stale, do not build from them without
re-checking each item against the live code first**, per this file's own
standing rule. Spot-checking a handful of its "MISSING"/"P0" claims found
three that are already done:

- **"`#wb-search` unwired, P0 bug"**, already deleted, `993e639` (see
  ROADMAP.md §0/§1).
- **"Deleting a note leaves whiteboard cards behind, no cascade"**, already
  swept: `autonomous.clean_orphaned_board_cards()`
  (`ai/autonomous.py:320-326`), covered by
  `test_a_card_whose_note_was_purged_is_swept_up`.
- **"Cards show raw truncated text, not the note's formatting" (flagged
  P0/P1, "clearest OneNote-fidelity gap")**, already fixed: card content
  renders through the app's real markdown renderer, not `textContent`
  (`app.js:28975-28997`, own comment documents the fix directly).

Given that hit rate, the rest of its gap matrix (mostly P2/P3 polish items)
should be treated as **candidate**, not verified, until someone re-runs the
same check live. What follows is only what was independently confirmed
against the current code, or was already tracked:

**Already brainstormed: see 29c, don't re-add:** board templates, layers
panel, frames/swimlanes, board version history, Mermaid text↔diagram both
directions, presentation/step-through mode, ink-to-text (already flagged
there as colliding with the no-torch constraint).

**Already scoped: see 29d:** links reaching an object, not just a card
(still open); rename/gallery/`generate_diagram` (done, HISTORY §61).

**Genuinely new, verified missing, not covered by 29c/29d:**
- ~~**Object lock**~~ **Built, see `core/database.py:1465` (`locked`) and [WHITEBOARD_PLAN.md](WHITEBOARD_PLAN.md) decision 15.** No `locked` column on nodes/sketches/objects today
  (checked `core/database.py`). Cheap: one boolean per table, a toggle in
  the Properties panel.
- **Numeric X/Y/W/H/rotation entry**: **Pointer:** `scratchpad/audit1005/features.md` section 4 row C3 (P2, the Format panel, Phase B). Confirmed no
  such inputs exist in `index.html` today; only drag-based resize/rotate.
- **A swatches/saved-palette panel**: **Pointer:** `scratchpad/audit1005/features.md` section 4 row C9 and section 8.2 kind 3 (saved styles and palettes, P1). Shared across stroke/fill/text-colour
  pickers: confirmed nothing exists beyond the app's own accent-theme
  picker (unrelated). Every colour control today is an ad-hoc native
  `<input type=color>`.
- **Font family + bold/italic/underline for whiteboard text boxes**, **Pointer:** `scratchpad/audit1005/features.md` section 4 row C10 (bold and italic are built, `#wb-prop-bold`; family is P2). 
  confirmed only font size exists today.
- ~~**Connector/link labels** on whiteboard links~~ **Built, see [WHITEBOARD_PLAN.md](WHITEBOARD_PLAN.md) decision 13 and `scratchpad/audit1005/features.md` section 4 row C6.** Distinct from the Graph
  tab's link-reason field; whiteboard's own `WhiteboardSketch` link type
  has no label. Would matter if `generate_diagram` output is ever meant to
  carry relationship text ("depends on," "leads to"), not just a line.
- **AI-readability additions**: **Pointer:** `scratchpad/audit1005/features.md` Phase G (FEAT-12 tools; the outline export is row C14 to C18, P2). Extending what `readwhiteboard`/
  `searchwhiteboard`/`generate_diagram` already do (`ai/tools/__init__.py`): an
  outline-text export mode (Mermaid-adjacent, for the AI or a human to read
  a board as a flat description); a semantic (embedding-based) index over
  whiteboard text-box content, since `searchwhiteboard` is keyword-only
  today; letting `generate_diagram` extend an existing board's cards as
  parent context, not just create fresh ones.
- ~~**Orphaned media garbage collection**~~ **Built, see `core/media_gc.py:196` (`find_orphaned_media`, dry run first); it misses board backgrounds (`scratchpad/audit1005/features.md` FEAT-06).** Confirmed still genuinely
  missing (no `clean_orphaned_media`-shaped function anywhere), unlike the
  card-cascade claim above which turned out to already be fixed.
- Smaller polish items: **Decided 2026-10-11, WHITEBOARD_PLAN decision 40** (Alt resizes from the centre; flip, opacity and the status bar recorded with reasons). **Pointer:** `scratchpad/audit1005/features.md` section 4 rows C3 (resize from centre, flip), C9 (whole-object opacity) and C13 (status bar); the contextual quick bar is built (`.wb-context`). The spec's Part C lists and a live check didn't
  contradict, kept for reference rather than re-verified line by line:
  resize-from-center, flip h/v, whole-object opacity, a status bar
  (zoom/tool/item-count), a contextual quick-action bar near a fresh
  selection.

**Not adopting**, matching the spec's own reasoning: full vector path/anchor
editing (Illustrator's actual product category, wrong tool for a
mindmapping app), real-time multi-user collaboration (contradicts this
project's single-user/local-first design principle), handwriting/math ink
recognition (no stylus-first workflow in evidence), image trace/pattern
fills/mesh gradients (print-design-tier, no tie to this app's use case).

---


## 29b. Carried out of the §40 audit

Full context in [../ROADMAP.md §40](../ROADMAP.md#40-the-antigravity-audit);
the features these attach to are described in §39. Companions:
[ANALYSIS.md](ANALYSIS.md) · [HISTORY.md](HISTORY.md) ·
[HANDOVER.md](HANDOVER.md).

Ranked. The first two are the same problem wearing two hats, a feature that
changes the app's behaviour without showing the user what it did:

1. ~~**A memory-stream screen.**~~ **Built**, Settings → The AI → *What it
   remembers*. Original entry kept for the reasoning:
   `save_user_preference` lets the model write
   standing instructions into its own future system prompts. There is no UI:
   the user cannot list them, edit one, or turn one off. The `user_preferences.
   active` column exists precisely for that and nothing sets it. Small piece of
   work, and it is the difference between a helpful feature and an
   unexplainable one.
3. ~~**Whiteboard cards outlive their notes.**~~ **Done**,
   `autonomous.clean_orphaned_board_cards`, beside the vector sweep.
4. ~~**`graph_local` costs a full notebook scan** to draw a local neighbourhood.~~
   **Done** 2026-10-04: the index is built from columns and kept per notebook
   version (HISTORY.md, "Moved from the backlog, 2026-10-04", section 29b).
5. ~~**PageRank runs on every `/graph` call, uncached.**~~ **Done**: see
   ROADMAP.md §0/§9 item 2: `routes_graph.py:60-105` caches pagerank/
   similarity by a notebook fingerprint, invalidated on write or embedding-
   model switch: exactly the "invalidation on write rather than a TTL" this
   item asked for.
6. ~~**`/media/{filename}` serves uploads same-origin with no type restriction.**~~
   **Done**: allowlist on upload *and* on serve, plus `Content-Disposition`.
   Original reasoning:
   No traversal, the name goes through `safe_filename`, but an uploaded
   `.svg` or `.html` is served from the app's own origin, and the AI can write
   here too. A `Content-Disposition: attachment` and an extension allowlist.
7. ~~**Decide on `edit_note` being destructive.**~~ **Decided, see `ai/tools/__init__.py:3243` (`edit_note` is deliberately not destructive, with three recorded reasons, and its change event carries an Undo).** See ANALYSIS §34b.

---

## 62. Extract notes: from the Writing Room, Documents, and Graph selections

**Built, preview-first.** `ai/extractor.py` (`propose_split`,
`merge_near_duplicates`), `POST /entries/extract/preview` and
`/entries/extract/commit`, and one shared preview modal wired to the Writing
Room, Documents and the whiteboard, plus, since §85, the **text-selection
kebab**, which made it reachable from any prose in the app rather than only
those three surfaces. 21 tests in `tests/test_extract_notes.py`. Full
resolution note in [HISTORY.md](HISTORY.md).

**Still not verified:** the AI's actual splitting, categorising and
link-reasoning judgement against a real model, this sandbox has no Ollama, so
only the fake-transport tests exercise it.

## 63. Ship a starter skills library, DONE, this claim was stale

Built: the detail moved to [HISTORY.md](HISTORY.md) ("Retired from the live files, 2026-09-07"). Kept for its number.

## 64. Documents editor: built, moved to HISTORY.md

The slash menu (`editor.js`) and focus mode (`toggleDocFocus`, `#doc-focus-bar`)
both exist; the rest of the pass lives in DOCUMENTS_PLAN.md. Kept for its number.

## 65. Highlight/web-clip capture

From the Kortex read (ANALYSIS.md §66): a way to save a highlighted passage
from something read elsewhere straight into a searchable note.

**Half built (§85).** The capture surface exists and is the piece this item
called small: highlight any prose in the app, open the selection kebab (⋯),
and **"Save with its source"** appears whenever the passage came from the web
reader: saving it as a markdown blockquote with a real link back to the page.
`clippingMarkdown`/`selectionSource` in `app.js`. The passage is quoted rather
than pasted flat on purpose: a clipping is somebody else's words, and a
notebook that cannot tell them from yours is worse than one that refuses
clippings.

**Source as metadata is built** (`Entry.source_url` and `source_title`, the
"from the web" badge in `note-cards.js`). **Still open, and deliberately separate:**

- **Sources outside the app.** **Next:** `Entry.source_url`/`source_title` exist (`note-cards.js:1859` draws the badge); the paste-a-highlight box is a small dialog in `frontend/js/capture-ask.js` with a text, a URL and a title field posting the same fields on `POST /entries`, built from DESIGN.md's dialog recipe; the browser clipper (WORLD_CLASS_PLAN D9, `routes_webclip.py`) covers the in-browser half and belongs to the clipper agent. Today the only surface that knows where a
  passage came from is the built-in web reader. A passage pasted in from a
  real browser, a PDF reader or a Kindle arrives with no origin at all, and
  nothing asks for one. The smallest useful next step is a paste-a-highlight
  box that takes the text *and* a URL/title by hand. **(needs Opus)**: a new
  capture surface, so a design call.
- **A Readwise/Kindle importer**: **Pointer:** the imports agent (section 115 row 1 is the importer set; Readwise is not on it, so size it there first). It is a genuine integration and should be sized
  separately before anyone commits to it. **(needs owner)**
  **Sized 2026-10-11 (data-1011), still needs the owner:** two readers in `entry/app_import.py` (`readwise`: the CSV with Highlight, Book Title, Book Author, Note, Location, Highlighted at; `kindle`: `My Clippings.txt`, blocks split on `==========`), a note per book keyed by a hash of title and author, a button each in Settings, Import & export, about 150 lines and two test files. The open question is a re-import: the clippings file only grows, and the rule that a note already here is left alone would skip a book that gained highlights. Recommendation: a note per book, and a re-import appends only the highlights not already in it, which needs the writer to merge into a source-keyed note (a new capability).

## 75. Voice memos: capture, storage, playback, and a dedicated library page

Asked for directly. `/entries/{id}/files` now has a real allowlist
(`ATTACHMENT_SUFFIXES` in `routes_files.py`, images, PDF, common office
formats, text and code, refusing anything else with a 415, e.g. video), but
audio is deliberately not on that list yet, there is no player anywhere in
the app, so an uploaded `.mp3` would just be a file nobody could listen to.
Three separable pieces, roughly in the order they'd need building: (1) a
record-a-voice-memo control (browser `MediaRecorder`, saved as an
attachment once `.mp3`/`.wav`/`.m4a`/`.webm` are added to the allowlist and
a size ceiling suited to audio rather than documents is picked, 50MB is
generous for a PDF and stingy for 20 minutes of audio), (2) an `<audio>`
player wherever an attachment is already rendered inline (the note card,
the lightbox), and (3) a Library subtab alongside AI Skills/Whiteboards/
Image Gallery listing every audio attachment across the notebook, the way
`routes_library.py`'s `_notes()`/`_archive()`/`_shelved()` already do for
images via `thumb_by_entry`. Meeting notes were the specific use case
raised: a memo recorded during a meeting, attached to that note.
**(needs Opus)**: the recorder exists for meetings (`media.js`), but audio is
still off the attachment allowlist (`routes_files.py`) and there is no player
or Library page; a new surface, so a design call.
**Next:** add `.mp3 .wav .m4a .webm .ogg` to `ATTACHMENT_SUFFIXES` (`routes_files.py:72`) with an audio size ceiling and `Content-Disposition: attachment` on serve; an `<audio controls>` in `note-cards.js`'s attachment row and the lightbox; a Library sub-tab in `library.js` listing them; the recorder is `media.js`'s meeting recorder.

## 76. Keyword-only note filing while the AI is unavailable, flagged for later AI review

**Built, both halves** (2026-10-05, HISTORY.md "backlog-1005"). The filer is
`manager.WORDS_FILED` and `lexical_filing`; the review is
`janitor.review_words_filed`, called by the background pass in
`ai/autonomous.py`. `tests/test_words_review.py`.

## 77. Notes-tab pagination and page-aware note links

Asked for directly: a large notebook's Notes tab is one continuously growing
list rather than a paged view with a page-size choice and a page selector.

**The performance half is done and is NOT this item (§86).** `renderEntries`
now renders in chunks as you scroll (`renderIncrementally`), so the DOM is
proportional to what you have scrolled past rather than to the notebook,
measured at 1,501 notes as 533 ms → 16 ms and 31,680 → 4,306 nodes. That
deliberately keeps the list **one continuous scroll**, which is the thing this
item distinguishes itself from.

**Item 1 is now built. Item 2 is still open and scoped below.**

1. ~~A page-size preference and a page selector top and bottom.~~ **Built.**
   `#notes-page-size` (All / 25 / 50 / 100, default All, today's continuous
   scroll, untouched) sits beside the existing Sort control; choosing a
   number replaces the scroll with one flat page and a Prev/Next bar
   (`#notes-pagination`) below the list. Persisted in `localStorage`, the
   same pattern as the graph's gravity/spread sliders. Deliberately kept
   separate from §86's `renderIncrementally` chunking: that stays the "All"
   path's implementation, unmodified. `paginateNotesForDisplay()`
   (`app.js`) is the one seam both the flat-sort list and the threaded list
   pass through, so a page can never overrun its slice.
   **One accepted trade-off, not a bug**: a thread can split across a page
   boundary (a parent on page 2, a continuation on page 3), pagination
   slices the already-flattened `[entry, depth]` order rather than keeping
   threads whole across page boundaries, matching the same "small, don't
   over-build this" scope this item's own text asked for. Verified live in
   Chromium: 120 seeded notes at 25/page → 5 pages, Prev disabled on page 1,
   Next/Prev step correctly, switching back to "All" restores the original
   60-item scroll window with zero console errors. `test_frontend_ids.py`,
   `test_frontend_handlers.py`, `test_style_scale.py` all still pass.
   **Follow-up, fixed the same session, and worth recording because it wasn't
   really about this one select.** Reported directly: the page-size dropdown
   didn't match Sort's height/alignment. Measured before touching anything,
   height and font-size already matched exactly (both inherit
   `.library-toolbar select`'s shared sizing rule), the real bug was width:
   the global `select { width: 100% }` base rule (`01-forms-settings.css`)
   is correct for a form field and wrong in a flex toolbar, and it only
   showed up here because this was the first `<select>` crowded enough to
   land *alone* on a wrapped line, with siblings to flex-shrink against
   (Sort, sharing a line with five other controls) the same 100% preferred
   width just never mattered before. `.library-toolbar select { width: auto
   }` fixes it at the toolbar level, not per-control, so the next crowded
   `<select>` added here inherits the fix rather than re-discovering the bug.
~~2. **The hard half: a wiki-link click has to land on the right *page*.**~~
   **Built.** `flashEntry` (app.js) already answered the design question
   this item was scoped around: it resets category, drafts and search to
   whatever the target's own view needs *before* it draws anything, a
   jump always lands in that reset default view, never in whichever
   filter the *origin* (Chat, the graph, a document) happened to have
   active, since most origins have no Notes-tab filter state to preserve
   in the first place. With that view fixed, the only thing missing was
   the page number.

   `orderedNotesForCurrentView()` is `renderEntries`'s own order:
   flat-sorted or thread-flattened, whichever the current search/sort
   picks: pulled out so there is exactly one place that decides "what
   order do these notes render in," used both to paint the list and to
   answer "which page is note N on." Deliberately **not** used to replace
   `renderEntries`'s own inline copy of the same logic: that render path
   is live, tested, and previously verified with real numbers (§86,
   §77 item 1); rewriting it to consume a shared helper risked a working
   feature for a refactor with no user-visible gain, so the small
   duplication was accepted instead. `resolveNotePage(id)` walks that
   order, finds the note, and divides by the active page size, "All"
   (no pagination) always answers page 1. Returns `null` for a note the
   current filters would hide entirely, which `flashEntry` treats as "stay
   on whatever page you're on" rather than lying about a page number.

   **Live-verified, both branches.** 61 flat notes, 25/page: starting on
   page 1, clicking a wiki-link to the oldest (page-3) note lands on
   "Page 3 of 3" with that exact note flashed. The harder case: the one
   this item's own text worried about, a thread **child** whose page
   depends on its *parent's* position, not its own sort key, verified
   separately: a parent buried under 55 newer notes, its child linked to
   directly, correctly resolves to "Page 3 of 3" with the child itself
   (not the parent) flashed and `.thread-child` still set. Zero console
   errors either run.

## 78. Whether the backend needs more concurrency than it already has

**Answered by the code, in the §85 audit, nothing to build.** Route handlers
are sync `def` on purpose: 238 sync against 1 async across `routes_*.py`, so
FastAPI runs every one of them in a threadpool and blocking IO inside them is
correct rather than a bug. SQLite is in WAL with `busy_timeout=5000`, so a
background job overlapping a page load is routine. The async-httpx item in §20
is a smaller and more optional change than this section assumed.

## 79. Linux release packaging: done; macOS still open

Asked for directly. Linux: built: `packaging/linux/memorymap.spec` +
`build-linux-package` in `.github/workflows/release.yml`, zipping a
PyInstaller onedir build (no installer format needed the way Windows
needs Inno Setup). Ships **without** the system tray: `_start_tray` runs
pystray's event loop on a background thread while `webview.start()`
blocks the main one, which the code's own comment says only Windows'
backend is known to tolerate, Linux's GTK backend has the same
main-thread-only constraint that already ruled out macOS, so the tray
call is now gated to `sys.platform == "win32"` rather than guessing.
Icon is `icon-512.png`, not the `.ico` (never confirmed GdkPixbuf decodes
it). Unverified until the Linux CI job actually runs, per this project's
standing rule for anything PyInstaller, it doesn't cross-compile.

**macOS is possible but has a real barrier beyond code.** An unsigned
`.app` triggers Gatekeeper's "app is damaged" warning on a current
macOS, not a bug, a deliberate OS policy, so shipping one that
actually opens for someone else requires an Apple Developer account
($99/year) and a notarization step in CI, not just a PyInstaller/DMG
build. Also inherits the same tray/threading question above and would
need its own answer, not an assumption it behaves like Linux. Worth
deciding deliberately rather than discovering after building the rest.
**Next:** `packaging/macos/` does not exist; the Apple Developer account and notarization are the owner's, so nothing is buildable here (the Linux spec, `packaging/linux/memorymap.spec`, is the template).

- (Odysseus, fourth read 2026-10-10) 

---

---

## 79b. New items, raised by the §85/§86 audit, not yet triaged

Logged rather than built. Each was found while doing something else, so none
has been scoped; they are here so the finding is not lost with the session.

- **Chat history has retention; nothing else does.** §86 added
  `conversation_retention_days` (off by default, pinned chats exempt). The
  same question is unasked for `AuditLog`, `entry_revisions` and the task
  history: all three grow monotonically, and `entry_revisions` in particular
  keeps a full copy of a note's text on every edit. Nobody has measured which
  of them actually gets large in a year of real use, and that measurement
  should come before any policy. **(needs owner)**: it needs a year of real
  data, or the owner's call on a policy.
  **Next:** a read-only script in `scratchpad/` that prints row counts and bytes for `audit_log`, `entry_revisions` and the task history on the owner's own notebook is the measurement the policy waits for.
- ~~**A support-bundle size ceiling.**~~ **Checked, not needed.** This entry's
  own premise ("no cap") was wrong: `core/logbuffer.py` already bounds every
  input to the bundle, `MAX_RECORDS = 500`, each message truncated to
  `MAX_MESSAGE_CHARS = 2000`, each trace sliced to 8000 chars in
  `BufferHandler.emit`, so `logs.json` tops out around ~5MB uncompressed in
  the worst case, and `preferences.json`/`status.json`/`counts.json`
  (`routes_settings.support_bundle`) are all small, fixed-shape payloads with
  no user-content field that could grow unbounded. No ceiling to add; grep
  before building would have found this.
- ~~**`GET /entries?semantic=true` now has two callers**~~ **Checked 2026-10-05: still two callers (`library.js:407` and `notes-list.js:3029`), so there is nothing to extract until a third appears.** (The Notes tab and, as
  of §86, the Library). The fetch-and-cache shape in `refreshLibrarySemantic`
  is the one to extract if a third appears, the command palette is the
  obvious candidate.
- **Semantic search still has no meaning for four of the five Library kinds.**
  §86 shipped the honest version, meaning-matching for notes, words for
  documents, chats, images and skills, and the control says so. The real
  question it defers: *should* documents be embedded? They are the one other
  kind with substantial prose, and embedding them would make "find the
  document about X" work the way notes already do. Not obviously worth the
  index size; worth deciding rather than leaving implicit. **(needs owner)**
  **Next:** documents are not embedded (`core/database.py` has `EmbeddingRecord` and `ChunkVector` for entries only, checked 2026-10-05); the owner decides, then `search/index.py` already indexes documents for keywords and a `DocumentVector` table would follow `ChunkVector`'s shape.
- ~~**The document-textarea resize fix has never been seen working.**~~ **Moot:** the document body is the CodeMirror surface (DOCUMENTS_PLAN Phase 2); the textarea `#doc-content` is only the fallback when the bundle fails to load, so there is no native resize handle to verify on the path anyone uses (HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)").
- **A naive orphaned-CSS sweep produces 33 false positives.** Classes built by
  template (`heat-${n}`, `library-${kind}`, `priority-${p}`,
  `result-reason-${r}`, `plan-step-${s}`, `outline-h${n}`, `graph-edge-${k}`)
  look dead to any grep for the literal string. Three genuinely dead rules
  were removed in §86; anyone re-running that sweep should expect the same 33
  and not delete them.
- **Compression/archival for rarely-used notes, documents, files and
  chats. (needs owner)** **Pointer:** the same decision as section 26 ("Note compression" and "Opt-in retention rules"); `media_gc.py`'s dry-run-first posture is the template. Asked for directly: let the user compress content they don't
  touch much and restore it on demand, at three possible granularities,
  one item, a whole space, or a group matched by some rule, with chat
  conversations floated as a candidate too. Worth doing, but genuinely
  underspecified before it's buildable, and the open questions matter more
  than the mechanism:
  - **What "compressed" means here.** Gzipping a markdown row saves little
    (SQLite text compresses well already at the filesystem/backup level,
    and notes/documents are what semantic search, the graph and the AI's
    retrieved context all read directly, compressing the row means every
    one of those needs a decompress-on-read path, or has to skip
    compressed items, which is a correctness change dressed as a storage
    optimisation). What plausibly does help: `MediaUpload` files
    (whiteboard photos, attachments) are actual binary weight, so
    archiving *those*: moving cold files to a separate on-disk location,
    or genuinely compressing image bytes, is the more defensible half of
    this idea.
  - **What "rarely used" means.** `Entry.access_count` already exists and
    is the obvious signal, but nothing currently reads it for this
    purpose; a real design needs a threshold (count, or count-since-last-N-
    days) and a way to preview what would be archived before it happens.
  - **Automatic-by-criteria is the riskier half.** A background job that
    silently archives content on its own schedule needs to be very sure it
    never removes something the user is about to look for, at minimum a
    dry-run/preview step and an easy bulk-restore, closer in spirit to
    `media_gc.py`'s existing "dry run first, refuse rather than guess"
    posture than to a fire-and-forget cron job.
  - Chat conversations specifically are already the cheapest form of this:
    they are pure JSON text with no embeddings or graph edges pointing at
    them, so "compress" there could mean something as simple as excluding
    older, unpinned conversations from the default list view rather than
    an actual archive format, worth deciding before building either.
- **Can the AI read chat conversation history?** Partly already built and
  worth knowing about rather than reopening blind: an agent-mode tool
  (`ai/tools/__init__.py`, searches `Conversation.title`/`.messages` by
  keyword) already lets the AI look up *other* saved chats by name/topic,
  built specifically because "each turn only ever saw its own thread, so
  the assistant had no memory of anything said in a different chat." Two
  real gaps remain: it's an agent-mode tool, so it isn't reachable from a
  plain conversational chat unless tools are enabled; and it searches by
  keyword rather than being handed relevant history proactively the way
  notes are via retrieval. Extending keyword search to embedding-based
  recall, or surfacing it outside agent mode, is the open half of this.
  **(needs Opus)**: a retrieval-design question (what is handed in, at what
  token cost), not a mechanical fix.
  **Next:** `search_chat_history` is in the registry now (`ai/tools/__init__.py`); the embedding half is section 95 item 8 (chat summaries as retrieval targets), the same `search/index.py` source registration.

---

## §95: the forward list

Asked for directly: *"brainstorm new features and improvements… what features
are missing, what should be added, what new capabilities?"* Written after a
session that read most of the codebase, so these are shaped by what is
actually there rather than by what a notes app generally has.

**Ranked by (what it unlocks) ÷ (what it costs), not by size.** Anything
already built is excluded, five items were dropped from this list during
writing for exactly that reason, which is the standing lesson of this file.

### A. Model and backend

1. ~~**llama.cpp, properly framed.**~~ **Built for the `/props` half, see `ai/openai_client.py:241-271` (`n_ctx` from llama-server's `/props`) and README.md:192; whether to bundle in-process `llama-cpp-python` stays a decision for the owner (a per-accelerator wheel matrix).** Now item A in ROADMAP.md. The app already
   speaks to `llama-server`; what is missing is saying so, detecting it via
   `/props` (which reports the real `n_ctx`), and *then* deciding whether
   in-process `llama-cpp-python` is worth a per-accelerator wheel matrix.
~~2. **Model health card.**~~ **Built (§97).** Settings → Models' existing
   spec table (size, quantisation, window, capabilities) now has a plain-
   language line under it: "a long chat will start dropping its earliest
   messages after roughly N exchanges", computed client-side from
   `usable_context` using the same shares `ai/context.py` uses server-side
   (an estimate, not a promise, an average exchange length is itself a
   guess). Banded at the edges: a very small window says so without a
   number, a very large one says it won't run out.
~~3. **Per-task model routing, made explicit.**~~ **Built (§97).** Settings →
   Background tasks' finished-jobs list already carried the model name
   (`taskhistory.record`'s `name` param, set by captioning and OCR already)
   but never rendered it, one line in `renderTaskHistory` (app.js) to show
   it next to the timestamp. Also added `name=` to the autonomous-pass
   recording (it used the utility model but never said so).
4. **A "this model is struggling" signal.** **Next:** the probe is `_tools_path_is_broken` in `ai/ollama_client.py:571` (§94); count its verdicts per model in the turn state and emit an `offer_tool_free` event after two, rendered as a one-line card with a button in `frontend/js/chat-agent.js`; harness agent's area (WORLD_CLASS_PLAN B5). §94 added a probe that tells a
   broken tools path from an outage. The same signal could be surfaced:
   after two tool-path failures on one model, offer the tool-free mode
   rather than silently degrading each turn.

### B. Retrieval and context: where the real quality ceiling is

5. ~~**Show the context budget in the UI.**~~ **Built, see `frontend/js/chat.js:425` (the meter's tooltip lists System prompt, Tool schemas, History and Notes plus question, in tokens).** `context.plan` already rations
   every part of the prompt and logs it. The chat has a percentage meter but
   no breakdown, so "why didn't it see my note?" is unanswerable without the
   log. A hover on the meter showing *system / notes / history / reply* is
   nearly free and answers the single most common AI complaint.
~~6. **Recency and pinning as retrieval signals.**~~ **Built (§97).** A
   third ranked list: the hybrid candidates reordered by pinned-first,
   then most-recently-touched: fused (RRF, by rank position, same as the
   existing semantic/keyword fusion) into the two `search_manager.py`
   already had. Deliberately a *reorder of candidates a real search already
   found*, never a new source of matches: a pinned note unrelated to the
   question is not a better answer to it. New test proves it (two notes
   tied exactly on relevance, pinning the older one flips the tie-break
   that would otherwise always favour the newer id).
7. **Re-rank the top N with the utility model.** **Next:** same item as section 11's "Re-ranking" (nothing re-ranks in `src/`); the seam is `search/engine.py`'s fused list. Hybrid search picks eight
   notes; a 1B model scoring those eight for actual relevance to the question
   costs one short call and is the standard fix for "it quoted the wrong
   note".
8. **Conversation summaries as retrieval targets.** **Next:** register a `chat` source in `search/index.py` (`source_for` raises on an unregistered kind by design) over the summary `compress_chat` stores, so `GET /search` and the agent's `search_notes` reach it. `compress_chat` writes
   summaries; nothing searches them. A question about something discussed a
   month ago cannot reach it unless a note was made.

### C. Capture: the half the app is named for

9. **Web clipper.** **Pointer:** WORLD_CLASS_PLAN D9 "Links and the web clipper"; the clipper agent owns it. `read_url` exists server-side; there is no bookmarklet or
   share target, so saving a page means copy-paste.
10. **Email-in.** **Next:** a decision for the owner: an IMAP poll is a second outbound connection, and `routes_settings.py:220` and `dashboard.js:1277` both say web search is the one feature that goes online (see INBOX 303's recommendation, section "Placed from INBOX" below, for the same trade). A local IMAP poller filing into a category is a well-worn
    pattern and turns the app into a capture destination rather than a place
    you go.
~~11. **Recurring notes / templates with dates.**~~ **Mostly already built,
    fixed the rest (§97).** `applyTemplate()` (app.js) already resolves a
    literal `{date}` token against any template's content: built-in
    ("Journal, {date}") or custom, via a plain string replace, so a
    daily-note template already worked. What was missing was
    *discoverability*: nothing in the Templates settings "Add your own" UI
    said the token existed. Added a one-line tip under the custom-template
    textarea. True recurrence (auto-create on a schedule) is still not
    built and would be a separate, larger feature.
12. **Voice capture beyond dictation.** **Next:** `mic-note` dictates into the capture box and Save files it (two clicks); a one-tap "record a thought" is `routes_voice.py` `/voice/transcribe` followed by `POST /entries` from a dashboard tile (`dashboard.js` quick actions), with the meeting recorder as the template. faster-whisper is already an extra.
    A "record a thought" button that transcribes *and* files is a different
    feature from dictating into a box.

### D. Trust and safety

~~13. **Private notes need an audit trail.**~~ **Already built when checked
    (§97, HANDOVER.md).** `get_entry` (routes_entries.py) already logs
    `"decrypted"` for a private note read while the vault is unlocked,
    this item was stale, not the code.
~~14. **Export a single note/document.**~~ **Built (§97).** `GET
    /entries/{id}/export.md`, mirroring the document route already in
    place: same title-as-H1 preamble (skipped when the note already
    starts with one), same filename sanitising. A "Download .md" item on
    a note's own overflow menu (Notes tab) and its Library "All"-view
    card menu, in the same spot the Document kind's own copy already
    sits. 4 new tests (`test_api_entries.py`).
15. **A dry-run mode for the agent.** **Pointer:** WORLD_CLASS_PLAN B5 (planner, verifier, per-run undo); `ai/autonomous.py:132` holds the autonomous dry-run's shape. `make_plan` shows intent, but a user
    who wants "tell me what you would change without changing it" has to
    trust the plan. A mode that collects the writes and shows a diff before
    committing would make destructive skills usable by people who currently
    avoid agent mode.

### E. Polish worth doing as one pass

~~16. **A real empty state for every tab.**~~ **Partially done (§97).** The
    Library's three subtabs that sit beside "All" (Documents, Whiteboards,
    Image Gallery) had a bare one-line `<p class="muted">` where "All"
    itself already had the icon+title `.empty-state` component: fixed to
    match. Along the way, found and fixed a real bug the source read alone
    would have missed: `renderLibraryDocuments()`/
    `renderLibraryBoardsGallery()` overwrote the empty-state element's
    `textContent` on every render (to show the "no search match" message),
    which silently wiped out the new icon+title markup the instant the
    function ran: the rich version would have shown for one frame, then
    been replaced by plain text. Fixed by giving the "no results for this
    search" case its own sibling element (`*-no-match`), matching the
    pattern the Image Gallery subtab already used correctly. Verified live:
    genuine-empty (icon+title), no-search-match (plain text), and had-results
    all screenshotted. Chat sidebar's `#conv-empty` and the Documents tab's
    own `#doc-empty` were deliberately left as plain text, narrow sidebar
    lists, not grid panes, so the same treatment would look oversized;
    unlike the three fixed, no user report named them.
~~17. **Keyboard-first navigation.**~~ **Already built when checked (§97).**
    `initEntryListKeyboardNav()` (app.js) already does Up/Down roving-
    tabindex movement between note cards and Enter-to-edit, wired up and
    called at module load. Verified live (Playwright): focus, ArrowDown
    twice, ArrowUp back, Enter opened the note for editing, all correct.
    This entry was stale, not the code.
18. ~~**Undo for destructive skill runs.**~~ **Built**, the same item as section 21's "Undo the whole run" (`undoSkillRun`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)").
19. ~~**`app.js` is 22,000 lines.**~~ **Built, see CLAUDE.md section 7 ("`app.js` is 25 files") and `frontend/js/chat.js`, `documents.js`, `library.js`, `dashboard.js`, `settings.js`.** The clean first extraction is `chat.js`
    (~3,300 contiguous lines: ask, the chat tab, image attachment, the agent
    timeline, the dock disclosure), following the §88.3 pattern that already
    produced documents.js, library.js, dashboard.js and settings.js. No
    user-visible gain, so it waits behind anything on this list that has one.
~~20. **Backup retention should be a setting.**~~ **Built.** Settings → Data
    → "Keep this many backups" (`#backup-retention`), a real preference that
    prunes immediately on change, was a hard-coded, always-enforced cap
    before.

### Deliberately not on this list

- **Sync / multi-device.** It is the most-asked-for thing in every notebook
  app and it is the one that would break this one: the app's premise is that
  the data never leaves the machine, and every sync design either weakens
  that or adds a server. If it is ever done it needs its own decision, not a
  backlog line.
- **A plugin system.** Skills already cover the "make the app do a new thing"
  case without a new extension surface to secure.

---

## §96: Guides, and diagrams the whiteboard can take

Asked for directly, and the two halves belong together: both are about the AI
producing *structured* output the user then owns.

### Guides: curated instructions the AI writes to

A **Guide** is a named, editable instruction set the AI pulls in when it is
writing: how to scaffold an academic assignment, how this user wants LaTeX
written, when a mermaid diagram is the right answer, a house style for
meeting notes. Ships with curated ones; the user can edit any of them and add
their own.

**Why it is not a persona and not a skill**, which is the design question:

- A **persona** changes *voice* and applies to everything.
- A **skill** is a *procedure* the agent runs, start to finish.
- A **Guide** is a *format contract* for one piece of output, it does not run,
  it constrains. Several can apply at once (an assignment guide + a LaTeX
  guide), which neither of the others allows.

Shape:

- Stored like skills (a table, editable in Settings), with a name, a trigger
  hint, and the instruction body.
- **Selected, not always-on.** Attached explicitly in the composer or the
  document editor, and *offered* by the same deterministic matcher the tool
  focus uses (`ai/toolwords.py`), which already tells "write my assignment"
  from "what is an assignment". Prompt budget is the reason: guides are prose,
  prose is the fixed cost `§94` just spent a release cutting, and a guide that
  silently attaches itself would undo that.
- Budgeted the same way everything else is (`ai/context.py`), with its own
  share, so a long guide crowds out notes visibly rather than silently.
- Applies to all three surfaces the user named: chat replies, note drafting,
  and `POST /documents/{id}/ai-edit`.

**Open question worth answering before building:** whether a guide should be
able to carry *examples* (few-shot) as well as instructions. Examples work far
better on small models and cost far more tokens, probably a per-guide flag
rather than a global decision.

**Next (checked 2026-10-05, no `Guide` table or code exists):** a `Guide` table and Alembic revision (`core/database.py`), built-ins in a new `ai/guides.py`, a deterministic offer through `ai/toolwords.py`, its own share in `ai/context.py`, a Settings pane beside Skills, a composer chip and the document editor's AI edit; no row in any plan, so add one to CHAT_PLAN first. Large.

### Diagrams: mermaid as the interchange format

The user's framing is the right one and worth keeping exactly: the AI writes
**mermaid**, the user previews and edits the mermaid, and only when they are
happy is it *exported* to the whiteboard as real cards, boxes and connectors,
**with the mermaid kept**, so it can be re-edited or reused later.

That ordering matters. `generate_diagram` already exists and writes straight
to the whiteboard, which means a wrong diagram is a mess to undo. Mermaid as
an intermediate makes the AI's output a *text artefact the user owns*: cheap to
regenerate, diffable, editable by hand, and portable out of this app entirely.

Work, in order:

1. ~~**Render mermaid where markdown already renders.**~~ **Built for documents** (a ```mermaid flowchart fence drawn as an SVG figure in Read and Live: `mermaidFlowParse`, `docRenderMermaidIn`, `tests/test_doc_mermaid.py`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)"). **Open:** chat and notes still show a mermaid fence as code (notes render at boot; subgraphs and other diagram types are not drawn).
2. **A preview + edit step**, the mermaid on one side, the rendered diagram on
   the other. The document editor's Split view is the same shape and can be
   reused rather than rebuilt.
3. ~~**Export to whiteboard**: mermaid AST -> whiteboard cards, shapes and links.~~ **Built** (`wbMermaidParse`, `wbMermaidLayout` in `whiteboard-interchange.js`, with frames as subgraphs; `tests/test_wb_interchange.py`).
4. ~~**Keep the source.**~~ **Built** (a board's SVG export keeps its Mermaid inside the file).

**Pointer:** `scratchpad/audit1005/features.md` section 10 (Documents D3) and section 4 row C6 and Phase E. Documents and boards render and import Mermaid (steps 1, 3 and 4 above); the AI-writes-mermaid-then-preview flow (step 2) and chat and notes rendering are what is left.

**The owner, 2026-10-06, verbatim:** "also does the whiteboard handle and export
in mermaid.js?? can the ai generate diagrams for export, download and opeining
in the whiteboard (may need heavy guidance)?? maybe this should go in the
roadmap". Answer: yes for import and export (flowcharts and subgraphs, built
above); no for the AI step. Placed as the next diagram work, in order:

5. **The AI writes Mermaid, heavily guided.** A built-in skill "Draw a
   diagram" with a house style and few-shot examples per kind (flowchart,
   mind map, sequence, timeline), a small-model-safe subset (flowchart TD/LR,
   subgraphs, labelled edges, no styling directives), and a verifier:
   `wbMermaidParse` must accept the text, every node must be reachable and
   labels at most 40 characters, else one re-prompt with the parser's error,
   then a plain failure. Replaces `generate_diagram` writing straight to the
   board.
6. **Preview, then act**: the step 2 split view, with three actions: Open in
   whiteboard (a new board via `wbMermaidLayout`, the source kept), Download
   (`.mmd` and `.svg`) and Copy.
7. **Wider Mermaid**: sequence and timeline diagrams render in documents and
   chat, and import to boards as frames; anything else stays as code.

**The owner, 2026-10-06, verbatim:** "I think mermaid.js should be better
integrated and expanded with the features, add to roadmap as well". This
reopens DOCUMENTS_PLAN decision 3 ("No Mermaid is vendored"), by the owner.
New decision: **vendor mermaid.js** into `frontend/vendor/` (MIT, so it may
come into this AGPL project with its notice; never fetched from a CDN, the
fully-local rule holds), **lazy-loaded** only when a diagram is on screen (it
is large; never in the boot scripts or their gzip budget), with
`securityLevel: "strict"` and no HTML labels (the CSP and the
`test_no_innerhtml_interpolation` rule). The in-house flowchart parser stays
as the board import path (`wbMermaidParse`) and the verifier in step 5.

8. ~~**Every Mermaid kind renders** where Markdown renders.~~ **Built** for documents (Read, Live, print, HTML export), chat and Ask replies (HISTORY.md, "Moved from the plans, 2026-10-27 (mermaid)"). **Open:** note previews (notes render through the editor surface, not `renderMarkdown`).
9. **A Mermaid editor**: a Live and Split view for a fence (source beside the
   drawing, errors inline with the line), snippets per kind from the "/" menu,
   and a "Diagram" block in the document toolbar.
10. **Boards and mind maps both ways**: a mind map exports to and imports
    from Mermaid `mindmap`; sequence and timeline import as frames with
    shapes; a board frame can be "Copy as Mermaid".
11. **Export**: any diagram to SVG and PNG, the `.mmd` source, and Mermaid
    kept inside the exported SVG (as boards already do); a diagram in a
    document exports with the document (PDF, HTML, DOCX as an image).
12. **The AI**: steps 5 and 6 above use the full renderer for the preview;
    the agent gets a `render_mermaid` check tool so it can see its own parse
    errors; Ask can answer with a diagram when the question asks for one.
12a. **Editing diagrams with the AI** (the owner, 2026-10-06, verbatim: "also
    editing diagrams as well like with the ai assistant in the document
    editor. rendering diagrams in chat messages etc"). The document editor's
    AI assistant works on a diagram as it does on a paragraph: select a
    diagram (or put the cursor in its fence) and ask ("add a step for
    review", "turn this into a sequence diagram", "group these into two
    subgraphs"); the reply is a Mermaid diff shown as before and after
    drawings, Accept or Discard, one Undo. The same on a board frame and a
    mind map branch (through their Mermaid form). Every proposal passes the
    step 5 verifier before it is shown.
12b. **Diagrams in chat, Ask and documents** (the owner: "as well as the
    documents"): ~~a ` ```mermaid ` block is drawn, and a block that fails to parse shows as code with the parser's one-line reason~~ **Built** (HISTORY.md, "Moved from the plans, 2026-10-27 (mermaid)"). **Open:** Copy, Download (SVG, PNG, `.mmd`), Open in whiteboard and Insert into a document under the figure's ⋯ menu, and Split view's drawing.
12c. **A diagram maker in the whiteboard** (the owner, 2026-10-06, verbatim:
    "a specialise diagram maker in the whiteboard with assisted and easier
    creation"). A third board kind beside Board and Mind map, "Diagram",
    built on the board's own shapes and connectors (no second canvas):
    - **Kinds** with their own shape set and layout: flowchart, org chart,
      swimlane process, sequence, ER, state, network; picked in the New board
      dialog (the 715 picker) with a template each.
    - **Easier creation**: hover a shape for four + handles that add a
      connected shape in that direction; Tab adds a child, Enter a sibling,
      typing replaces the label; connectors route orthogonally round shapes
      and stay attached when shapes move; alignment guides and even spacing
      snap; one "Tidy layout" re-runs the kind's layout (`wbMermaidLayout`
      grown into per-kind layouts).
    - **Typed creation**: a text box that turns "Start -> Check -> Done" or an
      indented outline into shapes and links as you type.
    - **Assisted**: "Describe a diagram" drafts one through the step 5 skill,
      previewed (step 6) before it lands; selected shapes can be asked to
      change (step 12a).
    - **Two-way Mermaid**: a side panel shows the diagram's Mermaid and edits
      in either side update the other; export as in step 11.
    - **Accessible**: every shape reachable by arrow keys along its links, a
      text outline of the diagram for screen readers, labels never below the
      4.5:1 contrast line.
12d. **INBOX 1410, the owner 2026-10-27, verbatim:** "can the ai and composer make mermaid diagrams?? cna it be
    wired and integrated into all the main features?? a way for the user to easily build and edit them?"
    Placed here: steps 9 (editor), 10 (boards and maps), 12 and 12a (the AI and composer draft and edit
    through the verifier), 12b (every surface) and 12c (diagram maker) are that ask; next, step 8 now built.
13. ~~**Tests and guards**~~ **Built** (`tests/test_mermaid_frame.py`: lazy, licence row, the frame's own CSP with the page CSP unchanged, the message protocol; `scratchpad/ui-sweeps/mermaid.js`: one of each kind in light and dark, no console errors).

### Related, and cheap: finish the rendering story

Checked this session: chat, documents and the dashboard digest all go through
`renderMarkdown`, but **notes deliberately do not** (see the comment at
`app.js:3791`). Documents now render a mermaid flowchart and highlight code
(CodeMirror); chat and notes do neither. Before
any of the above, worth settling as one pass: which surfaces render markdown,
whether code blocks get syntax highlighting, and whether notes should join,
because "the AI wrote a diagram and I can't see it" and "my code block is
grey" are the same gap.

## §98: reported live during the §90.2 small-screen pass, logged not built

Four asks landed while the small-screen audit was running. Two were built the
same session (the capture-composer `?` guide; the gallery-menu clipping fix,
both in HANDOVER.md). These are the ones deliberately left open, with what was
already checked so the next session does not re-derive it.

1. ~~**Collapsible / dropdown blocks at small screen sizes.**~~ **Pointer: superseded by UI_MODERNISATION_PLAN Phase 11 (gate `scratchpad/ui-sweeps/phonechrome.js`; WORLD_CLASS_PLAN section 1.7) and DOCUMENTS_PLAN Phase 6; the Settings modal at phone width is built (HISTORY.md).** Asked for
   directly, and deferred by the same message: *"some element blocks can
   collapse and become dropdown menus, or can have left right buttons to move
   left and right."* This is the shape §90.2 (ROADMAP) was heading toward
   anyway, so treat it as that item's design direction rather than a separate
   one. **What the audit already measured, so it does not need re-running:**
   at 390px the tab bar is genuinely scrollable (`scrollWidth` 640 vs
   `clientWidth` 364) and `#notes-subtabs` likewise (591 vs 341): both now
   at least *look* scrollable (`.edge-fade`, built this session), which is the
   affordance half, not the restructure half. The dashboard heatmap's
   apparently-off-canvas cells were chased down and are a **false positive**
   (a deliberately horizontally-scrolling widget, scrolled to today by
   design). Library, Chat and Graph reported clean at both 390px and 820px.
   So the remaining work is a genuine layout restructure on the surfaces that
   are merely *cramped* rather than broken, the 17-section Settings modal and
   the document editor being the two named candidates, not a bug hunt.

2. ~~**Links in a note should show as a card, like an attached image or file.**~~ **Built, see `frontend/js/markdown.js:1109` (`linkCard`: the host and the path in words, no favicon fetch, `target=_blank` with `noopener`) and the "Link card" slash item (`editor.js:850`).**
   Asked as a question: *"if the user adds links to notes in the capture tab,
   can they show as a card like an attached image or file at the bottom??"*
   **Read this before scoping it, because two different things are called a
   "link" here and only one of them is missing.** A `[[wiki link]]` to another
   note *already* renders as a clickable chip on the saved note
   (`renderNoteText`/`renderInlineMarkdown`, app.js): that half exists and
   should not be rebuilt. What does not exist is a card for an **external
   URL**: paste `https://…` into a note and it renders as a plain inline
   link, with none of the treatment `#entry-attachment-chips` gives an
   attached file. The ask is for that shape, a card at the bottom of the
   note, beside the attachment chips. Open design questions, all real:
   whether the card is generated at save time or render time; whether it
   fetches anything (this app is **offline-first**, a card that needs a
   favicon or an OpenGraph title is a network call this project has spent
   real effort avoiding, so the honest default is a card built from the URL
   itself: host, path, and the link text the user typed); and whether
   removing the card removes the URL from the note's text, which is exactly
   the question `#entry-attachment-chips` already answered for images (it
   detaches the reference, it does not delete the upload) and should answer
   the same way for consistency.

3. ~~**The lightbox's bottom bar should do more.**~~ **Built**, a
   `.lightbox-actions` row: zoom out / a live % / zoom in / Fit, plus
   wheel-to-zoom (1x-6x), drag-to-pan once magnified, Copy text, and Save.
   Everything works off what `openLightbox` already receives, so it lights
   up for every caller rather than only the Library's richer items. The
   id-requiring actions below (describe with AI, re-run OCR, rename,
   delete) are the part **still open**, see the note at the end of this
   item. Original scoping kept:

3b. ~~**The lightbox's bottom bar should do more.**~~ **Built, see `frontend/js/lightbox-view.js:952` (`buildMoreMenu`: rename, describe with AI, read text two ways and delete, shown only when the caller passes a media id; the Library gallery does).** Asked directly: *"can you
   improve on and expand the capabilities and features at the bottom of the
   lightbox?"* Not scoped this session. **What is there today**, so the next
   session starts from fact rather than the screenshot: `openLightbox`
   (app.js:2560) builds a `.lightbox-meta` line (filename, and "3 of 12" when
   there is more than one item) and a `.lightbox-info` panel below it holding
   four optional fields: `infoFacts` (dimensions, date added, filename),
   `infoCaption`, `infoText` (OCR), and `infoByline`. So it is already an
   *information* surface and has no *actions* at all: no download, no delete,
   no rename, no "describe with AI", no rotate, no zoom, no copy-text. The
   obvious move is that the five actions the gallery kebab already offers
   (rename, describe with AI, read text with AI, read text offline, delete)
   should be reachable from the lightbox too, since the lightbox is where you
   are actually *looking* at the picture, the same "the action belongs where
   the decision is made" reasoning that put the caption and OCR text there in
   the first place. **This half is what is still open**, and it needs one
   piece of plumbing first: no caller passes a media `id` to `openLightbox`
   today, so the Library caller (`library.js:1810`) has to start passing one
   and each action has to hide itself when it is absent, the same optional-
   field pattern `caption`/`text`/`byline` already use. Zoom and pan, the
   other half named here, are **built** (see above).

4. **Meeting notes need a real home.** **Next:** the structured summary is built (`librarian.summarize_meeting`, `POST /voice/summarize`); what is left is speaker labels (nothing in `src/` diarizes, checked 2026-10-05) and the owner's decision on whether a meeting becomes a first-class kind (an Alembic revision). Asked directly: *"the Meeting notes
   feature still needs a way to be accessed and better utilised as well as
   managed in the library as rn it is only accessible through the
   dashboard."* **Checked before scoping, and the premise is partly out of
   date: read this first.** Meetings are *already* a Library filter chip
   (`library.js:129`, `{ key: "meeting", icon: "ph:video-camera", label:
   "Meetings" }`) with a live count and a working filter, implemented as a
   tag filter over notes rather than a real kind (`libraryKind === "meeting"`
   filters `i.kind === "note" && tags.includes("meeting")`, library.js:372)
   - a meeting note is a finished note, unlike a draft, which is why it is a
   chip and not a sub-tab. Recording is also already reachable from the
   command palette (`ph:microphone Record a meeting or lecture`,
   app.js:16106), not only the Dashboard, and app.js:16101 carries a comment
   recording an earlier ask to expand that popup into a proper surface.
   So the genuine remaining work is **not** "add it to the Library" and
   **not** "add a second entry point", both exist. It is the *"better
   utilised"* half, which is the unscoped one: what a meeting note should
   carry beyond a transcript (speakers, decisions, action items → reminders,
   a summary), and whether a meeting deserves to stop being a tagged note and
   become a first-class kind, which is a schema change with an Alembic
   migration behind it, and should be decided deliberately rather than
   drifted into. Scope that question first; the UI follows from the answer.

## §99: the lightbox as a showcase, and uploads split by file type

Reported live across several messages. The lightbox half is **partly built**
(see HANDOVER.md); the upload half is **logged, not built**, and is the
larger piece.

### What was built

Built: the detail moved to [HISTORY.md](HISTORY.md) ("Retired from the live files, 2026-09-07"). Kept for its number.

### Still open: the upload split, and what it collides with

Asked for directly: *"there should be an upload documents option in the
documents tab in the library for uploading files pdf, docx, spreadsheet,
code documents, md, text files etc. all uploaded files get split based on
their filetype between the documents and image gallery tabs in the library,
and all documents should be viewable and editable in the documents area."*

**Read this before starting, because there is a real constraint in the way
and it is a security boundary, not an oversight.** There are two allowlists:

- `ATTACHMENT_SUFFIXES` (routes_files.py) is broad: pdf/docx/xlsx/csv/md/
  txt/code/zip. Attachments are **downloaded**, never served inline, and
  already reach `docview.extract` via `GET /files/{id}/text`.
- `MEDIA_SUFFIXES` is images + PDF only, and its comment explains why: that
  folder **is served**, and *"the AI can write into this folder too, so 'the
  only person who can put a file here is the person at the keyboard' is not
  true."* It is an allowlist precisely because a missed denylist entry there
  is a served-file problem.

So "all uploaded files go to /media and get split by type in the Library"
cannot be done by widening `MEDIA_SUFFIXES`, that would put .html, .svg and
friends in a served directory the AI can write to. The honest shapes are:

1. **Route by type at upload time**: an image goes to `media/` (served,
   narrow allowlist, unchanged), anything else goes to the attachment/
   uploads path (never served inline) and the Library lists both, reading
   documents through the text extractor. Most work, least risk, and it is
   the one that matches how the app already stores each kind.
2. Widen `MEDIA_SUFFIXES` and harden serving (explicit `Content-Type`,
   `Content-Disposition: attachment`, a sandboxed CSP on that route).
   Smaller diff, but it re-opens a question this codebase already closed
   deliberately: do not take this one without saying so out loud.

**"Editable in the documents area" needs its own decision first.** The
preview is read-only because the text is *extracted*, `core/docview.py`'s
own docstring makes the point that editing would mean writing text back into
a format it was never in. Editing a .docx in place is not a feature this app
can honestly offer. What it *can* offer, and what is probably meant: **import
the extracted text as a real Tessellate document**, which is then editable
like any other, with the original file kept as the source. That is a
different feature from "edit the upload", and much more achievable, scope
it as import, not as in-place editing.

**Built 2026-10-05, the import shape this section recommends:** Library, Documents, the more menu, "Import a file as a document" (`frontend/index.html` `#library-docs-import`, `frontend/js/library.js` `importLibraryDocuments`) posts each chosen file to `POST /documents/import`, which extracts the text into an ordinary Document, redraws the list and offers Open on a single import; a file the server cannot read is named in its own toast without stopping the rest. Checked at 1440 and 390, light and dark, by `scratchpad/ui-sweeps/bl1005-docsimport.js`; `tests/test_library_docs_import.py` holds the markup, the handler and the help. The routing-by-type half of the ask (images to the gallery, everything else to Documents) is what the Files, Images and Documents sub-tabs plus this import already do; `MEDIA_SUFFIXES` is unchanged.

~~Also still open on the lightbox itself: the id-requiring actions (describe
with AI, re-run OCR, rename, delete)~~ **Built, see section 98 item 3b.**

## §101: the knowledge graph should be second nature to the AI, everywhere

Asked for directly: the AI should be able to "flawlessly and instantly jump
between notes, know their link reasons, know the context between notes,
understand their meaning and purpose... at a relatively low cost," across
every AI feature and especially search, not a new capability so much as a
demand that an existing one stop being partial and optional.

**This is not a fresh ask, it is §87.5 and §88.4 items 3–5, restated as a
requirement rather than a nice-to-have, and worth reading in that order
before scoping anything new:**

~~- **§87.5 (live list, this file)** already scoped typed, weighted links
  (`EntryLink.link_type`/strength) as the mechanism for "know their link
  reasons"~~ **First slice built**: `link_strength()`, wired into both
  `entry/paths.py` and `graph_expansion()`. Still open: the composite over
  shared tags/category/temporal proximity (§87.5's own text has the full
  split of what's done vs. not).
  **Built since (2026-10-04, [GRAPH_PLAN.md](GRAPH_PLAN.md) KG2):** `ai/relations.py` combines shared entities, shared neighbours, shared tags and written-close-in-time into one confidence with a stated reason per signal (`tests/test_relations_kg2.py`), so the composite is no longer open.
- **§88.4 items 1–2 (ROADMAP.md)** are the reason "jump between notes" is
  already partly real: `graph_expansion()` walks linked neighbours of a
  chat/ask question's top hits and is wired into every retrieval call
  (`_retrieve()`), not a special mode, the default path. **It now does
  weight *which* neighbour matters more**, §87.5's typed-link slice above,
  the two items being the same feature scoped from two different sides.
- **§88.4 item 3 ("memory is a surface, not a system")** **Pointer:** PLAN.md row A3 ("Memory with provenance"; Settings, The AI, What it remembers exists). Is the "understand
  their meaning and purpose" half at the *notebook* level, not just per-note
  - no tiered always-on/retrieved/session-only memory exists anywhere in
  `ai/` today.
~~- **§88.4 item 4 ("no token accounting per stage")**~~ **Built**: the "at a
  relatively low cost" half, and was the *prerequisite* to anything else
  here, not an independent item. A per-stage token estimate (system/tool
  schemas/history/notes) is now attached to every turn's stats and shown in
  the chat metadata line's tooltip, so a graph-expanded, link-weighted
  retrieval pass's actual cost can now be read off directly, turn by turn,
  rather than needing new instrumentation first.

**Not re-scoped here, on purpose, the order has now run two of its three
steps.** Writing a second, parallel design for "AI-native graph navigation"
without first building §88.4 item 4's measurement would have repeated this
project's own standing caution (§88.4's closing note: "every one of these
becomes a change nobody can prove helped"). The order that respects what is
already true: instrument (item 4, done) → weight links (§87.5's explicit
slice, done) → **re-measure whether `graph_expansion`'s existing walk got
better: still open, and now the actual next step**, not §87.5's remaining
derived-signal composite and not a new mechanism beside the one that
already runs on every retrieval call. This sandbox has no reachable model,
so that re-measurement needs a real Ollama and cannot happen here.

**Next:** `scratchpad/llama-dev.sh serve`, then run one fixed question set through `search/engine.py` with and without `graph_expansion` (`tests/eval/golden.py` is the golden set) and compare the right-note rank; real model only.

## §102: a live competitor read (Kortex, Granola, Mem.ai), audited before logging

This sandbox has working web access this session, earlier reads in this
project's history (§30, §59, §60, §88.2) were done blind, from supplied text
or with a network policy blocking outbound access. Asked directly to look at
Kortex, Granola and a "second-brain" app (Mem.ai: the most-cited product
making that exact claim) live and compare. A subagent did the web research;
**every finding it returned was then checked against this codebase before
being logged here**, per this file's own standing rule, two of its claims
were wrong and are corrected below rather than repeated. Kortex.co and
Granola.ai themselves were blocked by this sandbox's own egress proxy even
though general web search worked, so those two products are read from
reviews/docs pages, not a first-hand render, a real gap, not this session's
laziness.

**Corrected before logging: do not re-file these as gaps:**
- *"No way to scope a chat query to chosen notes"*, **false.** `note_ids`
  plus `attached_notes_only` (`routes_chat.py`) already do exactly this;
  `_attached_notes` already gates it through the same private-note check
  every other read path uses. The subagent's finding didn't check the
  running code, which is the exact trap CLAUDE.md warns about, recorded
  here so nobody re-runs into it from this angle.
- *"No import from other note apps"*, **overstated.** `POST
  /import/markdown` and `/import/directory` (`routes_settings.py`) already
  round-trip Obsidian-style frontmatter and import a whole folder tree.
  What's genuinely still missing is narrower: a Notion-specific importer
  (Notion's export is HTML+CSV by default, not the plain markdown this
  already reads) and any first-run *offer* to import during onboarding
  rather than a buried Settings action.

**Worth taking, ranked:**

1. **A live "rough bullets + transcript → merged note" capture flow** **Next:** `frontend/js/media.js`'s meeting overlay gets a bullets textarea during the recording and `librarian.summarize_meeting` (`ai/librarian.py:1128`) a second input; the merge is one more prompt there, tested on the fake transport; same item as section 109.3 item 4.
   (Granola's core loop). Today's voice-memo/meeting path
   (`routes_voice.transcribe_meeting`) transcribes; nothing lets a person
   type short notes *during* the recording and then merges those bullets
   with the full transcript into one structured note afterward. Since
   transcription is already local, the merge step is a local-LLM prompt,
   not a new dependency, the more contained version of item 2 below.
2. ~~**A structured summary block on a transcribed meeting**~~ **Built, see `ai/librarian.py:1128` (`summarize_meeting`), `POST /voice/summarize` and `saveMeetingNote()` (section 106 records it).** (Decisions /
   action items / owner / date), extracted once after transcription.
   Checked: `transcribe_meeting` returns a transcript with no such
   extraction step today. Same shape as `caption_and_store`'s
   write-once-after-upload pattern.
3. ~~**A persistent "related to this note" panel inside the note editor**~~ **Built (the section 109.3 table, row 2: it updates live while editing).**
   itself**, live while writing, not just the graph tab's link-suggestion
   flow, which is a separate mode a person has to go find. Cheap once
   scoped: the embedding-similarity query graph's own link-suggestion
   endpoint already runs already exists (`routes_entries.py` similarity
   scan); this would be a small, always-visible panel reading the same
   signal for whichever note is currently open.
4. ~~**Typed note templates with a fixed field schema**~~ **Built as note types, see `api/routes_properties.py` (`/note-types`, GRAPH_PLAN KG4: a `type:` property assigns one, fields are text, number, date, note, list and checkbox over the note's own frontmatter).** (Sales Call, 1:1,
   Standup: Granola ships ~29), distinct from Skills (free-form saved
   *prompts*). A template would pre-structure a note's headings/fields
   before AI touches it, rather than the AI free-writing a whole note from
   a prompt. Needs a real schema decision (stored as structured `Entry`
   metadata vs. just a markdown skeleton) before building.
5. **A quick-capture popup from the system tray**, **Partly built:** the tray's "New note" (`__main__.py:2046`) and the in-app quick note (`frontend/js/quick-note.js`, Alt+N, `DEFAULT_SHORTCUTS.quickNote`); the always-on-top second window is section 106's open item and needs a real Windows machine. The tray already
   exists (`__main__.py`) with several nav items; a hotkey/click that opens
   a tiny always-on-top composer (title + body, Enter to save) without
   raising the full window is small, purely local, and matches a pattern
   several competitors treat as table stakes.
6. ~~**Inline citations in chat answers that point back to a specific note**~~ **Built (section 109.3 table row 6), see `ai/grounding.py` (numbered citations resolved against the retrieved notes) and CHAT_PLAN Phase 1.**
   clickable to jump there. Tessellate's retrieval already knows which
   notes it drew on (`search_manager.retrieve_detailed`); what's unclear
   without a live model to check is whether the *rendered answer text*
   itself carries a per-claim link back to its source note, versus only a
   list of sources alongside the answer. Verify against a real chat turn
   before scoping further: may already be partially there.
7. **A dedicated, browsable highlights/clippings collection**, **Built 2026-10-05** (HISTORY.md, "backlog-1005"): the Library's Highlights chip and `has:highlight`. Distinct
   from an ordinary note. Checked: `app.js`'s own comment names this "the
   capture surface half of BACKLOG.md §65 (highlight/web-clip capture)",
   selecting text and capturing it as a note already works, but that
   capture becomes an ordinary note, not an entry in a separate,
   source-attributed quote library the way Kortex's is. Worth deciding
   whether that's a real gap or just a different (arguably more
   consistent-with-the-rest-of-the-app) design before building a second
   collection type.
8. **Basic local speaker separation on a transcript** **Next:** faster-whisper does not diarize and a diarization library pulls torch (CLAUDE.md section 7); the only no-dependency route is a pause-and-energy heuristic, unreliable, so this is the owner's call. (Speaker 1/2/3, no
   naming needed): checked, genuinely absent (`grep -i speaker` across
   `src/` is empty). A fully local diarization pass, if the transcription
   library already in use supports one, would be a real, contained
   improvement over a flat transcript with no turn-taking structure.
9. **A live, inline organization suggestion while typing** **Next:** `ai/passive_capture.py` and `frontend/js/tag-suggest.js` are the nearest seams; a debounced `POST` with the draft text returning a category and tags (`janitor`'s cheap path, no model) shown as one chip row under the capture box, opt-in behind a Settings switch with its '?'. (A tag/category
   chip appearing as you write), as an *optional* companion to, not a
   replacement for: the existing off-by-default, audited background
   auto-tag job. The batch job's conservatism (gated, logged, reviewable)
   is a deliberate design choice recorded elsewhere in this file and
   should stay the default; this would be an opt-in faster-feedback mode
   for someone who wants it.
10. **A one-click "synthesize these notes into a draft" action** **Next:** same item as section 26's synthesised export; a built-in skill (`ai/skills.py`) plus a button on the Graph's selection bar. 
    (Kortex's "Blogger"): a named button in the graph/note UI that pulls a
    chosen set of linked/selected notes into a cohesive long-form outline
    or draft, distinct from a person hand-writing that prompt themselves
    in chat today. The re-paste of this same competitor research (a later
    session) named this one specifically as missing from the list above,
    correctly; it isn't covered by any of items 1–9. `expandNoteIntoDocument`
    (app.js) is the nearest existing thing and only ever takes *one* note.

**Out of scope, and why, not filed as gaps:** calendar-integrated
auto-join of video calls (needs a cloud calendar account or a bot joining
the call); shared/collaborative workspaces (needs a multi-user server,
against the single-user/no-sync design); native mobile companion apps kept
in sync (needs cloud sync or a self-hosted server); meeting-platform-specific
speaker-name capture via a browser extension (the local, nameless version is
item 8 above instead).

## §103, reported live this session, and a batch of feature asks, logged, none built yet

1. **The Documents-list kebab menu reported visually broken, with a
   screenshot** (a teal-bordered box around "Preview" alone, then a
   separately-styled block for Rename/Download/Delete below it). **Not
   reproduced.** Tried live in this sandbox's Chromium: default light theme
   and dark mode (`applyThemeChoice('dark')`), both desktop (1400px) and
   phone (390px) width, on the exact menu the screenshot matches
   (`library.js`'s Documents sub-tab kebab, `wireEscapedActionMenu`,
   already reparented to `<body>` with a `position: fixed` placement
   computed from the opener's own rect). Every reproduction measured and
   screenshotted clean: one menu, one background, items evenly spaced, no
   overlap. One real but much smaller thing found along the way, not a
   match for the report: the escaped menu's background
   (`rgba(24,27,37,0.97)` in dark mode) is very slightly translucent, so a
   document row directly behind it is faintly visible through it, worth a
   fully-opaque background if this comes up again, but not what was
   photographed. The screenshot's teal accent and glassy look don't match
   this app's default palette, the same shape a prior session's Settings-
   modal-contrast report turned out to be ("the user's screenshots
   consistently show a custom teal accent, not the default indigo"),
   next report should include the browser/OS, whether a custom accent/
   glass setting is on, and the zoom level.
2. **The Library "All" tab needs more utility**, asked for broadly with
   several concrete examples worth splitting out:
   - ~~**Tag management: rename, merge, browse.**~~ **Built, see `frontend/js/tag-manager.js` (the Tags sheet and its bulk dialog, one Undo) and `api/routes_tags.py` (`/tags/rename`, `/merge`, `/delete`, `/bulk`).** `entry/manager.py` already
     has `rename_tag`/`delete_tag` (merge-by-rename: renaming to an
     existing tag's name merges into it) and `GET /tags` already returns
     every tag uncapped specifically so a management screen could reach all
     of them: but **no frontend "Tag Manager" screen calls any of this**
     (`grep -rn "Tag Manager\|renameTag" frontend/` is empty). The backend
     is the built half; the UI is the missing half.
   - ~~**Click a tag to see every note carrying it**~~ **Built, see `tag-manager.js` (Enter on a tag row shows its notes) and the `tag:` search operator.** Confirmed, partly
     built, from a different surface than asked about.** The dashboard's
     Tag Cloud widget (`renderTagCloudWidget`, `dashboard.js`) already does
     this: clicking a tag sets the Notes search box to the tag name,
     switches tabs, and filters. Real gap: it's a **text search** on the
     tag word, not a strict "notes tagged exactly X" filter (a note that
     merely mentions the word "work" in its body would also match), and
     it's reachable only from a Dashboard widget someone has to have
     added: not from the Library "All" tab's own tag chips, which is
     where this was actually asked about. The Library's `Tags 0` filter
     chip (seen in the Library toolbar) switches the grid to a *list of
     tags*, not straight to one tag's notes: confirm live before deciding
     whether that's the missing link or a third mechanism is needed.
   - ~~**Renaming a saved chat.**~~ **Already built, the prior session's
     own grep missed it because the function isn't named `renameConversation`.**
     The saved-chats list's kebab menu already has both "Rename" (a prompt
     dialog, `PUT /conversations/{id}`) and "Name with AI"
     (`POST /conversations/{id}/retitle`, `app.js` ~line 11252). Corrected
     here rather than left standing.
   - The broader "make more and easily access them" ask (drafts, chats,
     files, everything) needs a concrete list of what's missing per kind
     rather than one broad redesign, say what specifically, next time.
3. **Recording new meeting notes already works**, **Next:** ask the owner what "edit" means (re-transcribe, resume a paused recording, replay the audio); `openMeetingRecorder` in `frontend/js/media.js` keeps no audio after saving, so replay needs section 75's audio attachments first. (`openMeetingRecorder`,
   `Ctrl+Shift+R`). **Editing an existing one is unconfirmed**, a
   transcribed meeting presumably lands as an ordinary note or document,
   editable the normal way, but whether there's a dedicated "re-open this
   meeting" flow (re-transcribe, resume a paused recording, see the
   original audio again) was not checked this session. Scope by asking
   what "edit" should mean here before building anything.
4. **Whiteboard: curved lines and custom anchor points.** **Bends built** (WHITEBOARD_PLAN decision 30: every connector style takes bends, a grip per bend and a double-click on the line adds one, `.wb-link-waypoint-handle`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)"), and a shape's connection points follow its outline (`wbPortsForPath`, eight fixed anchors otherwise). **Still open:** an anchor point anywhere along an object's edge, not only at those points (`wbNearestAnchor` snaps to a discrete set). A freeform curved sketch tool is a separate, bigger ask (the sketch pad is raster).
~~5. **Whiteboard: bring-to-front / send-to-back for a selection.**~~
   **Built.** Turned out cheaper than it looked: every item already had a
   `z` column, unused for anything but a fixed value set at creation, and
   the render code already painted from it (`.style("z-index", d => d.z)`,
   both cards' and objects' own merge): so no schema change and no new
   render path, only the missing action. `wbSetZOrder(kind, item, toFront)`
   sets `z` to one past the current max/min among its layer's peers and
   saves via the existing PUT route, plugging into the existing undo stack
   as a "move" entry. Two new "Bring to Front"/"Send to Back" items in the
   right-click/long-press context menu, for a single selection or a whole
   multi-selection at once. **One real architectural limit, stated rather
   than hidden**: cards and objects share one HTML stacking context and
   interleave freely against each other; a sketch renders in a separate
   SVG layer underneath both, so it only ever reorders against other
   sketches: it can never be brought in front of a card. **Live-verified
   in Chromium**: two overlapping text objects created via the real API,
   the back one confirmed actually obscured (Playwright's own
   actionability check reported the front box "intercepts pointer
   events"), right-clicked → Bring to Front → the stacking visibly
   flipped, and the new `z` value survived a full page reload (read
   straight from `wbState` after a fresh navigation, not just checked
   in-memory).

## §105: Library "All" tab: the create button now follows the filter chip, the rest is scoped not built

Asked for directly: the create button at the top of the Library "All" tab
should change based on the active filter chip, "Create Note" on Notes,
"Create/Upload Document" on Documents, "New Chat" on Chats, "Transcribe
Audio" on Meetings, and a general "Create +" picker modal on "Everything",
plus more general capability to rename and create things (tags, categories,
chats) directly from the Library.

**Built:** the button now matches the active chip for the four kinds with
one unambiguous thing to create (Notes/Documents/Chats/Meetings:
`LIBRARY_CREATE_BY_KIND`, library.js). Verified live: switching chips
changes the label and the resulting action (Notes → Capture and focuses the
box; Documents → the existing new-document flow; Chats → a fresh
conversation; Meetings → the recorder). **Item 1 below is now also built**
(re-asked for directly in a later session): "Everything" and every other
ambiguous chip (Files, Tags, Drafts, Activity, the bin) now open a real
"What would you like to create?" modal (`openLibraryCreatePicker`,
library.js) instead of silently defaulting to "+ New note", a full overlay
rather than a `kebabMenu()` dropdown, since the button isn't wrapped in
`.menu-wrap` and `.library-view-section`'s own scroll-clipping is exactly
the trap `wireEscapedActionMenu` exists to work around elsewhere; a modal
sidesteps both rather than fighting them. Live-verified: opens on the
default "Everything" chip, lists all four kinds plus Cancel, picking one
runs it and closes, Escape and backdrop-click both cancel.

**Not built: logged rather than rushed:**
1. ~~**A "categories" section of the Library**~~ **Built as the Manage categories panel, see `frontend/js/categories-panel.js` (rename, merge, split, delete, new category; reachable from the palette, `palette.js:1383`, and the Notes sidebar); no Library chip was added.** It doesn't exist:
   `LIBRARY_KINDS` (library.js) has note/document/chat/file/tag/draft/
   meeting, no category. Cheaper than it sounds: `PUT` and `DELETE
   /categories/{id}` already exist (routes_categories.py), and
   `renameCategory()` (app.js) already renames one from the Notes tab's own
   sidebar: reusable as-is, not built from scratch. "Create an empty
   category" has no real meaning today (a Category row is created
   on-demand the first time a note is filed into it, `get_or_create_category`,
   entry/manager.py); a Library category view would need to decide whether
   that stays true or an empty category becomes a first-class creatable
   thing.
2. ~~**Renaming a tag "everywhere"**~~ **Built, see `api/routes_tags.py:76` (`POST /tags/rename`, merge-by-rename) and `tag-manager.js` (`renameTagEverywhere`).** It had no dedicated endpoint, tags are a
   JSON array on each `Entry`, not a table, so "rename this tag" today
   means editing it per-note. A real rename-everywhere action needs either
   a new endpoint that rewrites the tag across every entry carrying it, or
   a documented decision that it's out of scope and a tag is meant to be
   cheap to abandon and recreate rather than renamed in place.
3. **Creating a note/chat directly from the Library**, **Next:** `openLibraryCreatePicker` (`frontend/js/library.js`, `LIBRARY_CREATE_ORDER` at line 1932) gets a text field on its Note row that posts `POST /entries` and closes; the picker is a modal so it needs no dock change. Rather than jumping
   to the Notes/Chat tab. The create picker (built above) is the natural
   place to extend from, "type it right here" inside that same modal,
   rather than a separate affordance.

## §106: Links, Contents and note References built; §102 items 5 and 6 checked, not built as originally scoped

Asked for directly, three things together: can notes/documents reference
each other with a References section; a place to store/bookmark website
links; a table-of-contents-style hyperlinked, visualised view of the
notebook's structure. Checked first, per this file's own standing rule,
`[[wiki links]]` already covered note-to-note linking with autocomplete,
transclusion and backlink chips (`app.js`, extensively) and the Graph tab
already visualises links coloured/filtered by category. What was genuinely
missing: anywhere to save a link to the open web, and a fast textual outline
distinct from the Graph's spatial one.

**Built:**
- **A `Bookmark` model and `/bookmarks` CRUD** (`core/database.py`,
  `api/routes_bookmarks.py`), its own small table, not folded into `Entry`:
  a bookmark has no body to search, file, or auto-categorise, so forcing it
  through the note pipeline would solve a problem it doesn't have. URLs
  typed without a scheme ("example.com") are normalised to `https://`.
  Creating a URL that's already saved still creates the row and returns
  `duplicate_of` the existing one: warn, don't block, since re-saving a
  link by accident is normal, not a mistake worth refusing.
- **Grouping**, asked about directly ("should they be groupable?"): a free-
  text `group_name` column rather than a real folder table, a full nested-
  folder model (a tree table, drag-to-move UI) is a lot of new machinery for
  what a flat field mostly already buys. A "/" convention ("Work/Reading")
  the frontend renders as a visual hierarchy, still just one string. Filter
  chips above the list, a search box (client-side, matching the Image
  Gallery's own filter), pin-to-top, and edit/move/delete actions round out
  the Library → **Links** subtab.
- **A note's References**: a note can now attach a saved bookmark
  (`entry_bookmarks` join table, `POST/GET/DELETE /entries/{id}/bookmarks`),
  shown live in the edit form right below the related-notes panel, with an
  "Attach a link" picker. Its own small table and its own endpoint, not
  folded into `EntryLink` (which connects two `Entry` rows) or into
  `EntryOut`'s bulk-fetched `links` field, matching the precedent
  `/entries/{id}/related` already set: only the editor needs this, so it
  shouldn't grow a query on every paginated list render.
- **Library → Contents**: a hyperlinked outline of the notebook, grouped by
  category or by tag, click a note to jump straight to it. Built from
  `allEntries` (already loaded for the Notes tab) grouped client-side, not a
  new endpoint: refetched on every visit like every sibling Library subtab,
  not cached, since a stale outline (a just-deleted note still listed) would
  be a wrong answer, not just an old one. This is deliberately the *fast,
  scannable* half of "visualised links between sections and tags"; the
  *spatial* half is the Graph tab's job already, and Contents links out to
  it rather than duplicating a second visualisation engine.
- Live-verified in Chromium: add/pin/edit/group/delete a bookmark, filter by
  group and by search text, the duplicate-URL toast, both Contents modes
  grouping correctly and jumping to a note, and attaching/detaching a
  bookmark reference from a note's edit form: all measured, not assumed.
  One real bug caught this way and fixed before shipping: `ph-push-pin-fill`
  doesn't exist in this app's bundled Phosphor set (checked: only
  `push-pin`/`-slash`/`-simple`/`-simple-slash` do), so the pin button
  rendered blank: `-slash` for "already pinned" is the same pairing the
  pinned-chat button already uses.

**§102 item 5 (tray quick-capture), corrected rather than rebuilt:** the
tray's own "New note" item (`__main__.py`) already does the load-bearing
part of this ask, one click, past the lock screen, straight to a focused
empty note, no tab-hunting. What it does *not* do is the literal ask, "a
tiny always-on-top composer... without raising the full window", it raises
the full window. Not built this session, and deliberately not attempted
blind: a real floating composer needs a second `pywebview` window (a new
`webview.create_window()` call, its own minimal page, its own focus/close
semantics coordinated with the main window's lock state and the existing
tray event-loop threading, which `_start_tray`'s own docstring already
flags as delicate). This sandbox has no Windows, no `pywebview` runtime, and
no display at all for this code path, confirmed live: importing `pystray`
here raises `Xlib.error.DisplayNameError` on this headless box, the exact
failure `_start_tray`'s own except-clause already anticipates. Writing a new
window-management code path with zero ability to launch or see it is how a
"small" feature ships broken; needs a real Windows session to build safely.

**Next:** a second `webview.create_window` (always on top, no frame) from `_start_tray`'s `_new_note` (`__main__.py:2046`) opening `/#quick`, with `frontend/js/quick-note.js` as the page's one control; needs Windows to verify, so the owner's machine.

**Superseded: inline chat citations are built since (section 109.3, `ai/grounding.py`).** **§102 item 6 (inline chat citations), resolved, the answer was "no", found
by reading the code, not by needing a live model:** the retrieved notes sent
to the model are numbered in the prompt (`librarian.build_messages`, "1.
[category] ..."), but nothing in `GROUNDING` instructs the model to cite
that number, and the frontend's `#chat-results` list is a plain, separate
source list rendered alongside the answer, never parsed out of the answer
text itself. So: confirmed, not "unclear without a live model" any more:
there is no per-claim citation today, only a source list next to the
answer. Building real inline citations is a prompt-reliability question a
fake-transport test can't settle (would a small local model actually emit
`[1]`-style markers consistently enough to parse?), left open for a
session with a live Ollama/LM Studio to validate against, per this
project's own standing caveat about model-behaviour work. **Not chat-
specific**, asked about directly afterward: search summaries and the weekly
digest ground their prose in the same retrieved-notes-numbered-in-the-
prompt shape `librarian.build_messages` uses, with the same absence of a
citation instruction: so this is one cross-cutting gap across every place
the AI writes prose from notes, not three separate ones.

**Bookmarks elsewhere, asked about directly:** *Documents*, **built**:
`DocumentBookmark` (same shape as `EntryBookmark`, keyed to `document_id`
instead of `entry_id`), `GET/POST/DELETE /documents/{id}/bookmarks`, and a
**References** section in the document editor's own Outline sidebar tab
(next to Backlinks/Notes it draws on), with the same "Attach a link" picker
notes got. Live-verified in Chromium: attach, the reference chip opens the
URL, detach, and the picker correctly lists every saved bookmark regardless
of which note or document (if any) already references it. *Graph*:
recommended **against** adding bookmarks as graph nodes: the Graph is built
around note-to-note similarity and typed links, and a bookmark has no
content to compare against anything, so it would be a node with different
semantics bolted onto a visualisation designed around one kind of thing. A
small "has references" indicator on a note's own graph node is a
reasonable, much smaller alternative if this is picked up later, not built
this session.

**The Library "All" tab's create/upload buttons: confirmed still covered
by §105, not missed.** §105 above already logs this in full: the button now
follows the active filter chip for the four unambiguous kinds
(Notes/Documents/Chats/Meetings), and §105 item 1 already names the
remaining gap precisely: a real "choose what to create" picker for
Everything and every kind with no single obvious answer (Files, Tags,
Drafts, Activity, the bin), not yet built, with the open question being
dropdown-off-the-button vs. a real modal. Nothing new to add here; re-
reading §105 rather than re-logging it.

**A second competitor-analysis pass (Kortex/Granola/Mem.ai) was re-pasted
this session, from a different subagent run than §102's**: cross-checked
against §102 rather than logged as new, since it is the same three products
against the same feature list and overlaps almost entirely:
- Its items 1–4, 6, 8–10 are §102's items 1, 3, 7, 6, 5, 9, 10 respectively
  - already logged there, unchanged.
- Its item 5 ("import from other note apps") and item 7 ("chat query
  scoping via explicit note selection") are the two claims §102 already
  checked against the running code and corrected, false/overstated, see
  §102's own "Corrected before logging" block. Restated here only so a
  future session doesn't re-file them from this second paste without
  noticing §102 already settled them.
- Its item 11 ("structured decisions/action-items block on meeting notes")
  is §102 item 2, and item 2 is now **built** (this session, §25/§31 in
  the live task list): `librarian.summarize_meeting`, `POST
  /voice/summarize`, wired into `saveMeetingNote()`.
- Its item 12 ("speaker labeling on local transcripts") is §102 item 8,
  unchanged: still genuinely absent, still needs checking whether the
  transcription library in use supports local diarization at all before
  scoping further.

No new gaps in this second pass beyond what §102 already carries.

## §107: a fast live-report round: nav-history contrast, Contents redesign, a bookmark-edit gap, and three items logged not built

**Fixed, live-verified:**
- **The nav-history popup was unreadable in dark mode**, reported directly.
  Reproduced (dark theme, 20+ stack entries): rows were cramped (`gap:
  0.15rem`) with small text, reading as garbled at a glance even though
  the computed colour itself (`#e7e9ee` on `rgba(24,27,37,0.97)`) was fine
  - this was a spacing/size problem, not a contrast one. `.nav-history-menu`
  and `.nav-history-item` now use the standard spacing tokens and
  `--text-md`/`line-height: 1.6`. Confirmed legible after.
- **Contents redesigned**: reported as "ugly." Was bare headings and a
  flat link list with no containment; now a card grid
  (`.contents-outline` → CSS grid, one bordered `.contents-section` card
  per group), matching the card language `.bookmark-row`/`.outline-link`
  already use elsewhere.
- **A bookmark's Edit action only ever touched its title, not the URL**,
  reported directly. Now prompts for both (two sequential dialogs, matching
  the group button's own one-dialog-per-property shape, `promptDialog`
  only ever takes one field, so a combined dialog would be new machinery
  for a two-field edit that happens rarely).

~~**Noticed while fixing the above, not chased further:**~~ **Fixed since, see `frontend/js/navigation.js:982-1006` (`entryLabel` resolves `[data-target]` as well as `[data-section]`, so a Library sub-tab reads "Library: Contents").** The nav-history
popup's own label for a Library sub-tab visit can show the raw internal id
("Library → library-view-contents") instead of a friendly name,
`entryLabel()` looks up `[data-section="..."]`, but Library's sub-tabs
carry `data-target`, not `data-section`. Pre-existing for every Library
sub-tab, not something this session's Links/Contents additions introduced;
cosmetic, not chased given the session's remaining budget.

**Asked about directly, logged rather than built this pass:**
1. ~~**Whiteboard selection/move/copy UX**~~ **Built** ("highlight and select stuff and move it... copy elements and move them other places or to other boards... the whiteboard controls still feel annoying to use"): marquee, lasso, group resize and shift-select, the controls redesign (WHITEBOARD_PLAN Phases 1 to 4) and copy and paste across boards (`wbClipboard` survives a board switch); HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)".
2. ~~**The AI Skills tab's step/tool lists still read as unstyled**~~ **Fixed in section 108 (`.skill-fact-list`) and section 110.2 (the step numbers).**:
   reported directly, with a screenshot: numbered steps and the tool list
   render as plain paragraphs directly on the card background, with no
   visual container distinguishing them from the rest of the card (unlike
   the "N steps"/"N tools" chips above them, which are already styled).
   Not investigated or fixed this session, the markup/CSS for this
   specific sub-view wasn't located before the session's budget ran out;
   next session should grep `library.js` for the skill-card renderer
   (`renderSkillsDashboard` and neighbours) rather than re-diagnosing from
   scratch.
3. **Inline chat/search/digest citations, tray floating composer,
   templates, highlights collection, speaker diarization, live tag
   suggestions, one-click draft synthesis**, all still open exactly as
   §102/§106 already describe them; nothing new to add.
4. **Library's sub-tab bar asked to match Notes' own sub-tab styling:
   built.** Both shared the `.seg` base class, but only `.notes-subtabs`
   (05-sidebars-themes.css) layered the raised-card look on top of it
   (border, shadow, blur, sticky); `.library-subtabs`
   (07-whiteboard-misc.css) never got the same treatment and stayed the
   plainer generic pill. `.library-subtabs` now carries the same
   properties. Live-verified side-by-side in dark mode, matching now.

**Fixed in the same follow-up round, also live-verified:**
- **The nav-history popup's last row sat flush against the bottom edge**
  with no breathing room, unlike the clear gap above the first row, the
  container's own `padding-bottom` isn't reliably honoured past the end of
  a scrolled flex container's content in every engine. `.nav-history-item:
  last-child { margin-bottom: var(--space-2); }` is the robust fix.
- **Contents cards showed a stray horizontal scrollbar that cut off both a
  long filename and its hover highlight.** Only `overflow-y` was set on
  `.contents-list`, which: per the CSS spec's own computed-value rule for
  a box scrollable on one axis, silently turned `overflow-x` into `auto`
  too, so an unbroken filename with no wrap point forced the box wide
  instead of tall. Fixed with `overflow-x: hidden` plus
  `white-space: normal; overflow-wrap: anywhere` on the link itself, so a
  long name wraps onto a second line instead of forcing horizontal scroll.

**Reported, not reproduced: logged rather than guessed at:**
- **From INBOX 111's second batch (2026-09-09), still not reproduced live
  as of 2026-09-14:** the boards and maps widget's visual design, the AI
  skills sidebar not reaching full height, square tab corners, the chat
  panel shadow, and the light-versus-dark glass difference. Each needs a
  window size and a screenshot to become a bug; none has one.
- **The back-to-top button reportedly appears on a page that isn't
  scrollable.** Read `scrollTopTargetEl()`/the `update()` loop
  (app.js, ~L15949-16069): each tab's scroll target is either a nested
  container (`NESTED_SCROLL_TABS`) or that tab's own `.tab-page` element
  via `scrollingPage()`, and the show/hide condition is a plain
  `scrollTop > 400` check: nothing in this path obviously explains a
  false positive on a page with too little content to scroll 400px in the
  first place. A live repro attempt (scripted scroll + tab switch) did not
  reproduce it, but the scroll-trigger method used was itself suspect (the
  button never showed even on a tab confirmed scrollable), so this is an
  inconclusive negative, not a clean bill of health. Needs a real repro,
  which tab specifically, and whether it's on first load or after
  switching from an already-scrolled tab, before attempting a fix.

**New feature request, logged only, not scoped or built:**
- ~~**Highlighting text in notes and documents.**~~ **Built, see section 109.2 (`==highlight==`, with colours).** Asked for directly. Not
  investigated this session: needs its own pass to decide the storage
  shape (inline markup in the note/document's own text vs. a separate
  span-range table) and how it interacts with existing markdown rendering
  and the AI's own reading of note content, before scoping further.

## §108: a fast bug-fix round: three real front-end bugs and a batch of small polish

**Fixed, all traced to a root cause rather than patched blind:**
- **Nav-history popup, genuinely broken this time**, reproduced: a
  history of short single-word entries (a plain tab visit, no sub-section)
  shrank the popup's fit-content width down to a narrow, sub-pixel value
  (164.34px measured), and text that narrow inside a `text-overflow:
  ellipsis` flex child rendered as illegible marks rather than real
  glyphs: confirmed clean again at both a wider `min-width` and a higher
  device-pixel-ratio, so this was the popup's own sizing, not a font/theme
  regression. `min-width: min(14rem, 90vw)` keeps it out of that zone
  regardless of how short any one entry's own label is.
- **`#search-help` and `#capture-help`** were bespoke hand-rolled click
  toggles from before `initHelpToggle` existed, never migrated: missing
  the outside-click and Escape closes every *other* help toggle in the app
  gets (reported: "the capture a thought tooltip doesn't close when
  clicking off it"), and `search-help-hint` also carried its own one-off
  `.search-help` class instead of the shared `.graph-help-panel` floating
  look `capture-help-hint` already had (reported separately as a style
  mismatch between the two). Both now go through `initHelpToggle`; live-
  verified open/outside-click-close and confirmed `search-help-hint`
  carries `.graph-help-panel` now.
- **The AI Skills tab's step/tool lists**: reported directly, with a
  screenshot: expanded, they read as plain paragraphs sat right on the
  card background. `.skill-fact-list` now gets a bordered/backgrounded box
  of its own (`--chip-bg`, `--radius-md`), the same card-on-card language
  `.contents-section` uses.
- **The Graph options row's toggles** (Similarity/Entities/Documents/Hide
  unlinked/Labels) were bare switches with muted text, hard to tell where
  one control ended and the next began, reported directly, with a request
  to match the Semantic toggle's own look. All five now also carry
  `.checkbox-label`, the shared pill-chip class that toggle already had,
  same fix applied to two more bare `.tools-toggle`s found the same way
  (Agent mode, Settings → Logs' "Follow").
- **The lightbox's document preview panel** was translucent (`var(--card)`,
  deliberately glass) sitting over the lightbox's own darkened backdrop,
  reported as "somewhat transparent". Switched to `var(--modal-bg)`, the
  same near-opaque token every other floating overlay already reads text
  against.
- **`.library-subtabs button` was more rounded than `.notes-subtabs
  button`**, traced to cascade order, not a missing class: a global
  "user-tunable corner rounding" rule (`.seg button`,
  04-chat-dock-appearance.css) sets a bigger radius and loads *before*
  `.notes-subtabs button`'s own explicit `--radius-md` override, so Notes
  wins on load order while Library's own button rule (added this session,
  07-whiteboard-misc.css) never set the property at all and inherited the
  bigger one by default. Now sets it explicitly too.

**Built, asked for directly:**
- **A "Clear" button for the AI Skills sidebar's own log list**,
  `DELETE /audit?entity_type=...` (`entity_type` required, so this can
  never be a way to wipe the *whole* audit trail, note edits/deletes are
  real accountability history, not a scrollback buffer, only the one
  filtered slice a caller names). The sidebar's sticky/full-height/
  internal-scroll behaviour itself was **already built** in an earlier
  stretch of this session (checked before touching anything, per this
  file's own standing rule), only the clear action was actually missing.
- **Suggested-link reasons, the thing "Explain your existing links" was
  reported as not doing** (it never could: see that button's own long-
  standing comment): a new "Suggest reasons" button next to it,
  `POST /entries/link-suggestions/reasons`, fills each pending suggestion's
  empty Why box with an AI guess (best-effort per pair, degrades to an
  empty list rather than an error when the model is down). Kept the
  original backfill button rather than replacing it, it's a real, working,
  separate capability (reasons for links that already exist) the ask
  didn't say to remove.

**Bookmark URL editing**: re-checked after being reported again: the fix
from earlier this session (`library.js`'s bookmark Edit action prompting
for both title and URL) is still present and correct on disk. If still
seeing title-only editing, it's very likely a stale cached `app.js`/
`library.js`, this project's own history names exactly that trap
(HANDOVER.md, "a static-file cache header that let the desktop app run
yesterday's app.js").

**Still open, unchanged from §106/§107:** whiteboard select/move/copy-
between-boards UX, a tray floating composer, inline chat/search/digest
citations: all need either a live model, a Windows environment, or their
own scoping session, none of which this one has.

**Checked 2026-10-05:** inline citations are built (section 109.3, `ai/grounding.py`), copy between boards works in a session (`whiteboard.js:4832`), the rest stands.

## §109: the measured bug round, the competitor gap list triaged, and what is genuinely still open

Three things in this section: bugs fixed this session **with the measurement
that proved each one** (not a reading of the source), the twelve-item
competitor gap analysis triaged against what this app already has, and a
brainstormed list of what is missing that nobody has asked for yet.

### 109.1 Fixed, and how each was actually proven

The theme of this round: **four separate reports were "already fixed" by the
source and still wrong on screen, and one was never a bug at all.** Reading
the code decided none of them. What decided them was measuring.

- **The nav-history popup, reported four times** ("garbled overlapping
  text", "completely broken", "still broken", with screenshots). Every
  earlier fix: spacing, a `min-width` floor, a last-row margin, moving it
  out of the status bar's `backdrop-filter` stacking context: was aimed at
  the wrong cause, and each one was "verified" by *looking at a screenshot*,
  which is exactly how four rounds got spent on it.

  The actual cause, found by decoding the screenshot PNG and reading raw
  pixel values instead of trusting my own eyes on it: `--modal-bg` is
  `rgba(…, 0.96)`, i.e. **4% see-through by design**. Over most backdrops
  that is invisible. Over the note editor, the densest block of small text
  in the app: 4% is enough for the labels underneath to survive as legible
  ghosting, and any screenshot pipeline that rescales or recompresses
  amplifies it further. Sampled down the popup's left padding column, the
  background read `(252,253,255)` at the top and `(244,246,253)` lower down:
  a real, measurable ~8-unit gradient that was the form showing through.

  Fix: a new `--modal-bg-opaque` token (alpha 1) used by `.nav-history-menu`.
  Re-sampled after: every point reads `(252,253,255)` exactly, uniformly.
  `--modal-bg` itself is left alone, its other callers (Settings, the
  command palette) float over much emptier backdrops.

  **And that was only half of it.** The popup was reported broken *again*
  after the opacity fix, with a dark-mode screenshot showing the rows as
  scattered dashes. That is the "illegible dashes" symptom an earlier
  stretch of this session wrote off as a screenshot/DPI capture artifact,
  **that conclusion was wrong, and writing it off is what let the bug
  survive several more rounds.** Measured this time instead of looked at:
  each row reported `scrollHeight` 35px inside a 32.36px box, so the
  `overflow: hidden` on `.nav-history-item` was slicing every glyph down to
  its top few pixels, which is precisely what "dashes" were. The rows are
  `<button>`s, and the app's generic button rule pins a fixed control
  height; the menu escaped that while it lived inside `#status-bar` (whose
  own `.status-item` rules won) and stopped escaping when it was moved out
  to the body earlier in this same round. Fixed with `height: auto;
  min-height: 0` plus flex centring; re-measured `clipped: false`, and the
  dark-mode render is clean and fully legible.

  Two independent bugs presenting as one complaint, which is why each
  individual fix "didn't work", and why the report kept coming back.

  **The transferable lesson, and it is the important part of this section:**
  a screenshot viewed by eye is not evidence at this precision. Both a human
  and a vision model will read faint luminance gradients as "ghost text" or
  fail to see a real 4% blend depending on scaling. `scratchpad/pngpixel.py`
  (a ~50-line pure-Python PNG reader, no dependencies) samples exact pixels
  and is the tool to reach for whenever a report is about transparency,
  contrast, or a colour looking wrong. For anything about text being cut
  off, the equivalent is comparing `scrollHeight` against `clientHeight`,
  which settles in one number what rounds of staring at screenshots could
  not. **Never close a visual report as "a capture artifact" without a
  measurement that says so.**

- **The AI Skills sidebar, reported three times** ("still doesn't float and
  stay 100% the height of the screen"). The sticking was never broken,
  measured: scrolling its container by 400px left it pinned at y=196.97
  exactly. **The height was wrong.** `max-height: var(--page-sticky-h)`
  resolved to 655px, but this sidebar's scrolling ancestor is
  `#library-view-skills`, a *nested* scroller only 534px tall, so the card
  ran 121px past its own viewport and 52px below the fold on an 800px
  screen. `--page-sticky-h` is the right figure only for a sidebar whose
  scroller is the page (`.doc-sidebar`, where the pattern was copied from).
  Fixed with `container-type: size` on the scroller and `max-height: 100cqh`
  on the sidebar; measured after: 534.2px, bottom at 731, still pinned.

- **The Graph options separator** clashing with the "All time" read-out:
  the divider `::before` set only `margin-inline-end`, so it had the parent
  gap on one side and gap+space-3 on the other. Now `margin-inline`.

- **No caption byline in the lightbox**, the Library tile has carried one
  since captions became hand-editable; only the lightbox was missing its
  half, so the same picture named its transcriber but not its describer.
  Added, mirroring `syncCaptionBadge` exactly.

- **The OCR text in the image gallery** is now clamped and expandable like
  the caption above it, for both the Tesseract and the vision-model field.

- **Bookmark URL editing: not a bug, and this is the third report of it.**
  Reproduced the whole flow live in Chromium this time rather than grepping
  again: Edit opens "Title:" prefilled, saving opens "URL:" prefilled,
  changing both persists, and a full page reload still shows the new title
  and the new URL. The code is correct and the behaviour is correct.
  Everything points at a stale cached `library.js` on the reporting machine
  - the trap HANDOVER.md already names. **If it is reported a fourth time,
  do not re-read the handler; get the served file's ETag and the browser's
  actual loaded copy and compare them.**

- **The nav-history popup "doesn't appear in the Documents tab"**, does not
  reproduce. Measured in both Notes and Library→Documents: visible, correct
  box, `elementFromPoint` at its centre lands inside the menu (so nothing is
  covering it), no page errors. Same stale-cache suspicion as above.

### 109.2 Text highlighting: built

Built: the detail moved to [HISTORY.md](HISTORY.md) ("Retired from the live files, 2026-09-07"). Kept for its number.

### 109.3 The competitor gap analysis, triaged

The twelve-item Kortex/Granola/Mem read was checked against the app rather
than filed as-is. **Six of the twelve are already built**, which is the
same ratio an earlier audit found, and the reason this project's standing
rule exists. Do not rebuild these:

| # | Gap | Status |
| --- | --- | --- |
| 2 | Persistent related-notes panel in the editor | **Built**, updates live while editing, not just on click |
| 6 | Inline citations in AI answers | **Built**, answers carry the notes they came from |
| 8 | Global quick-capture from the system tray | **Built** |
| 11 | Structured decisions/action-items block on meeting notes | **Built**, prepended automatically on save |
| 4 | Highlights/clippings library | **Partly**, Links (bookmarks) shipped this session; quote-level highlights are not a library yet, but `==highlight==` now exists as the capture syntax |
| 7 | Chat query scoping to selected notes | **Partly**, notes can be hand-attached to a chat turn; there is no "search only these" scope toggle |

Genuinely open, ranked by value-per-effort:

1. ~~**Import from other note apps** (gap 5)~~ **Built 2026-10-05** (WORLD_CLASS_PLAN H6 and row 25; HISTORY.md, "Moved from the plans, 2026-10-05 (row 25, the importers and the keyboard)"): `POST /import/app` (`entry/app_import.py`) reads a Notion export (zip, HTML), an Obsidian vault, an Evernote `.enex` and an Apple Notes export, idempotent by source, links as `[[wiki links]]`, front-matter as tags; Markdown folders were built before (`/import/directory`, `/import/markdown`); `tests/test_app_import.py`, `tests/test_vault_import.py`. **Open, small:** attachments are not copied in (Evernote's `en-media` reads as "[attachment]"), and there is no dry-run preview before anything is written.
2. ~~**Typed note templates with structured fields**~~ **Built as note types (GRAPH_PLAN KG4, `api/routes_properties.py`).** (Gap 3): Skills are
   reusable *prompts*; this is a different thing: a category-bound field
   schema (decisions, owners, dates) that renders as a form and stores
   structured values. The meeting-summary block already proves the output
   shape is useful; this generalises it.
3. **Speaker labelling on transcripts** (gap 12): **Next:** same decision as section 102 item 8 (the owner). Transcription is already
   local, so "Speaker 1/2/3" by voice is an incremental local win. Named
   speakers need no platform integration if the user can rename a label once
   and have it stick for that recording.
4. **Rough notes + transcript merge** (gap 1): **Next:** see section 102 item 1. The two-stage capture
   Granola is built around. Recording, transcription and the summary block
   all exist; what is missing is the *merge* of the user's own bullets with
   the transcript into one note, which is one more local-model pass.
5. **"Compose a document from these notes"** (gap 10): **Next:** see section 102 item 10 and section 26. The agent can
   already do it from a hand-written prompt; this is a button on a graph or
   list selection, not new capability.
6. **Live organise-suggestions while typing** (gap 9): **Next:** see section 102 item 9. Offer it *alongside*
   the audited background librarian, never replacing it. The gating and the
   audit log are deliberate and must survive.

### 109.4 Brainstormed: not asked for, worth doing

- ~~**The selection popup in editors, decide, then build.**~~ **Built, see section 110.3 (it appears in the note editor now; only its dismissal while typing is watched).** Reported twice as
  "the ellipse kebab button doesn't appear when I highlight things", and now
  partly explained rather than guessed at. On *rendered* content it works:
  driven live against `.entry-content`, the popup appears with the right
  text. It does not appear in the note editor, and that is deliberate,
  `SELECTION_POPUP_EXCLUDED` is `"input, textarea, [contenteditable],
  .selection-popup"`, and the editor is a `<textarea>`.

  So this is a design decision, not a bug fix, which is why it is logged
  rather than half-built: **should selecting text inside the editor offer
  the same actions as selecting it on a note card?** The argument for is
  that the editor is exactly where you would want highlight-with-colour,
  "extract this to its own note" and "link this to…". The argument against
  is that a popup over a live cursor fights normal text editing. A textarea
  can supply the selection via `selectionStart`/`selectionEnd`, so the
  capability is cheap once the decision is made; the awkward part is
  dismissal behaviour while typing continues. Whoever picks this up: get
  that decision from the user first. **(needs owner)** Beyond
  fixing whatever regressed, selecting text is the natural home for
  highlight-with-colour, "ask the AI about this", "extract to a new note"
  and "link this to…". Today selection offers nothing consistent.
- **Highlights as a queryable collection.** **Built 2026-10-05** (HISTORY.md, "backlog-1005"): `has:highlight` (`search/engine.py`, answered from the row's own text) and a Library Highlights chip listing each passage with its note (`routes_library._highlights`, `entry/highlights.py`); no new table. Once `==highlight==` is in use,
  "show me everything I highlighted this month" is a search-index question,
  not a schema question, the marks are already in `content`. **(needs Opus)**
- **Search-result grouping by category/tag**, with counts, **Next:** `GET /search` (`api/routes_search.py`) already returns each hit's kind and category; grouping is a client fold in `frontend/js/palette.js` and the Library's search with a count per group, no backend change. The result list
  is flat however many hit. **(needs Opus)**
- **Per-note pinned AI context**, **Next:** `note_ids` and `attached_notes_only` (`routes_chat.py`) already scope a turn; a `Entry.pinned_context` boolean (Alembic) adds the note to every turn's `note_ids` in `librarian.build_messages`, with a note-menu toggle and a chip in the chat header. A note that is always in scope for chat
  ("my current project"), rather than relying on retrieval to find it. **(needs Opus)**

## §110: the toolbar round: formatting in Notes, and five more measured bugs

### 110.1 Built

Built: the detail moved to [HISTORY.md](HISTORY.md) ("Retired from the live files, 2026-09-07"). Kept for its number.

### 110.2 The five bugs, and the measurement that found each

- **Gallery kebab stayed open over the rename field.** The close-on-pick
  listener was on the bubble phase, with a comment explaining that each
  button's handler should run first, but every one of those handlers opens
  with `stopPropagation()` to keep the click off the tile beneath, so the
  click never reached the listener. Capture phase fixes it; closing the menu
  does not cancel the click still travelling to the button.
- **The graph dock's divider clashing with the time read-out**, reported
  twice and "fixed" once by reasoning. Measured: the group sat at exactly its
  300px `max-width` while the read-out's right edge was at 705px against a
  group edge of 698, **the label had overflowed its own box by 7px** and
  landed 2px from the next group. A flex item's automatic minimum size is its
  content, so `min-width: 4rem` on the slider did not make it the thing that
  gave way. Now it is. Re-measured: no overflow, 10px to the divider.
- **Skill step numbers clipped against the panel border**, four reports,
  three of them "fixed" by changing padding. An `outside` `::marker` hangs
  into the padding by an amount CSS at this level cannot bound, so no padding
  value was ever going to settle it. The numbers are now real spans in a
  two-column grid gutter: they cannot overhang, and wrapped steps align under
  their own text rather than under the number.
- **The Regenerate-greeting button wrapping onto its own line.** The (usually
  empty) status span had `flex: 1 1 auto`, giving it a 178px content basis:
  256 + 205 + 178 + gaps = 663px against a 656px row. A zero basis lets it
  take only what is left.
- **Bookmark URL editing, reported five times, working every time it was
  tested.** The handler was correct and the flow was reproduced end to end,
  including persistence through a reload, on every check. The fault was
  never in the code; it was that a second modal appearing only *after* you
  commit the first is a bad way to expose a second field, and anything that
  interrupts between them (a stale script, an Escape, a mis-click) leaves the
  URL never asked for and looks exactly like "editing the URL is broken".
  Now one inline form with all three fields visible at once. Separately,
  **every local css/js URL is version-stamped** (`?v=<version>`, pinned by
  `tests/test_asset_cache_busting.py`) so a stale cached `library.js` cannot
  survive a release: this project's most-repeated false bug report.

### 110.3 Still open

- **Whether the selection popup should appear in the note editor at all** is
  now moot: it does. What is *not* settled is its dismissal behaviour while
  typing continues; it currently follows the same rules as on rendered
  content. Watch for reports of it getting in the way mid-sentence.
- Everything in §109.3 (the triaged competitor gaps, **six of the twelve
  were already built, check that table first**) and §109.4.
- Highlights as a queryable collection, backlinks panel, conflict-safe
  editor, per-note pinned AI context, bulk tag editing, all §109.4.
  **Checked 2026-10-05:** the backlinks panel (`notes-list.js:3431`, `/entries/{id}/backlinks`), the conflict-safe editor (`frontend/js/edit-conflict.js`, a 409 dialog) and bulk tag editing (`tag-manager.js:674`) are built; the other two stand.

## §111: where this app should go next, grounded in what the code actually does

Asked for directly: missing features, inefficiencies, and future directions.
Everything below was checked against the codebase rather than imagined, and
anything already built is named as such so nobody rebuilds it.

### 111.1 Inefficiencies, measured or read rather than guessed

- **The notes list has no virtualisation, and every render rebuilds it.** **Partly built since:** `renderIncrementally` (`frontend/js/notes-list.js:2069`, section 86) paints in chunks as you scroll, so the DOM follows what was scrolled past; recycling rows that scroll away is not built. **Next:** a windowed list in `notes-list.js` (a spacer plus the visible slice, `IntersectionObserver` sentinels already exist there), measured with `scratchpad/ui-sweeps/` at 5,000 seeded notes. Original finding:
  `loadEntries` pages at `ENTRIES_PAGE_SIZE = 1000` but loops until it has
  *all* entries, and `renderEntries()` opens with `list.replaceChildren()`
  and then builds a node per entry. This file's own comments talk about a
  75k-note notebook; at that size this is 75,000 DOM nodes rebuilt on every
  filter keystroke, tag toggle and save. **This is the single biggest
  scalability item in the frontend** and it is invisible until someone has a
  big notebook, because it is fine at a few hundred. Windowing the list (or
  rendering only the filtered slice plus a sentinel) is the fix; the
  server-side pagination it needs already exists.
- **`/entries/link-suggestions/reasons` is sequential.** Up to twelve model
  round-trips one after another in a threadpool endpoint. Concurrency would
  not help much, a single local model serialises anyway, so the honest
  lever was the count, now capped at 6 automatically with the button for the
  rest. Worth revisiting only if someone runs a server that batches.
- **Filing costs a model round-trip per capture** since the order was
  reversed. Now a preference (`ai_first_filing`), so this is a *choice*
  rather than a cost, but it is worth measuring on a slow model before
  assuming the default suits everyone.
- **Three places independently decide what markdown means**: built 2026-10-11, DOCUMENTS_PLAN decision 13 (`MD_INLINE_MARKS`, read back through `INLINE_MD` by `tests/test_code_documents.py`).

### 111.2 Features worth building, ranked by value per unit of work

1. ~~**Import from other note apps.**~~ **Built 2026-10-05** (WORLD_CLASS_PLAN H6 and row 25; HISTORY.md, "Moved from the plans, 2026-10-05 (row 25, the importers and the keyboard)"): `POST /import/app` (`entry/app_import.py`) reads a Notion export (zip, HTML), an Obsidian vault, an Evernote `.enex` and an Apple Notes export, idempotent by source, links as `[[wiki links]]`, front-matter as tags; Markdown folders were built before (`/import/directory`, `/import/markdown`); `tests/test_app_import.py`, `tests/test_vault_import.py`. **Open, small:** attachments are not copied in (Evernote's `en-media` reads as "[attachment]"), and there is no dry-run preview before anything is written.
2. ~~**Backlinks on the note itself.**~~ **Built, see `frontend/js/notes-list.js:3431` and `menus.js:1002` (`GET /entries/{id}/backlinks`).** The graph already knows what links *to*
   a note; the note never shows it. Cheap, and it is half of what people mean
   by a connected notebook.
3. **Highlights as a queryable collection.** **Built 2026-10-05**, section 109.4 (HISTORY.md, "backlog-1005"). Now that `==highlight==` exists,
   "show me everything I highlighted this month" is a search-index question,
   not a schema one, the marks are already in `content`. This is also the
   honest version of the "clippings library" competitor gap (§109.3 item 4).
4. ~~**Export a single note or document** (Markdown/PDF).~~ **Built, see `api/routes_entries.py:2113` and `routes_documents.py:909` (`export.md`), `core/docexport.py`.** Backups export
   everything; there is no "send this one to someone".
5. ~~**Typed note templates with structured fields**~~ **Built as note types (GRAPH_PLAN KG4).** A category-bound schema
   (decisions, owners, dates) rendered as a form. The meeting-summary block
   already proves the output shape is useful; this generalises it. Skills are
   reusable *prompts*, which is a different thing.
6. ~~**Bulk tag editing**~~ **Built, see `frontend/js/tag-manager.js:674` (`openBulkTags`, one Undo).** From the notes list, with the same undo everything
   else has.
7. ~~**A keyboard-shortcut sheet.**~~ **Built, see `frontend/js/settings-wiring.js:1514` (`openShortcuts`, built from `DEFAULT_SHORTCUTS`, rebindable, `?` opens it).** `Ctrl+K`, zoom, dictation and the "/" menu
   all exist and nothing lists them in one place.
8. **Per-note pinned AI context**, **Built 2026-10-05**, section 109.4 (HISTORY.md, "backlog-1005"). A note that is always in scope for chat
   ("my current project"), instead of relying on retrieval to find it.
9. **Speaker labelling on transcripts.** **Next:** the owner's call, section 102 item 8. Transcription is already local, so
   "Speaker 1/2/3" by voice is incremental; letting a user rename a label
   once and having it stick for that recording covers the rest.
10. ~~**A conflict-safe editor.**~~ **Built, see `frontend/js/edit-conflict.js` and `api/edit_conflicts.py` (a save that lost a race comes back 409 and opens the compare dialog).** Two windows on the same note is silently
    last-write-wins today. Low frequency, high annoyance when it happens.

### 111.3 Directions, not features

- **Decide what the graph is *for*.** It is currently a picture plus a thing
  the AI can walk. The two uses pull in different directions, a human wants
  few, meaningful edges; retrieval wants many, weighted ones. Typed links and
  link strength (§87.5) are the lever, but the decision comes first.
- **The AI's honesty surface is the app's real differentiator.** Answers
  already carry the notes behind them and the librarian is audited and
  gated. Every future AI feature should be held to that bar, visible
  reasoning, an undo, and a log, rather than added as another silent
  automation.
- **Decide whether the note editor is a text box or an editor.** It now has
  a toolbar, a preview and a selection menu, while Documents has a full
  four-view editor. Either the composer stays deliberately small and defers
  to Documents for real writing, or the two converge. Drifting between the
  two is what produces a third dialect of markdown.

## §112: the strategic pass: what would make this app hard to compete with

Asked for directly: *"brainstorm the future of development for the app in the
roadmap and backlog, what features are missing, what needs to be done, fixed,
refined, scaled, refined, optimised and more. how can we professionalise the app
further and make it stand out from competitors"*, alongside the standing
instruction to make it *"something that hasn't been done before"* and *"valuable
that users would be willing to pay for"*.

§111 above is the previous pass and is still the honest inventory of
inefficiencies; this one is about **positioning**, and every claim here was
checked against the code rather than imagined.

### 112.1 The one thing this app has that the others structurally cannot

Every competitor in this category is either cloud-first with AI (Notion AI, Mem,
Reflect, Tana, NotebookLM, Saner) or local-first without it (Obsidian, Logseq,
Anytype, Zettlr). The first group cannot promise privacy because the model is
somebody else's server; the second cannot promise intelligence because there is
nothing to ask. **Tessellate is local-first *and* has a model**, and that is not a
feature list: it is a category of its own, and almost nothing in the product
currently *says* so.

The strategic mistake to avoid is competing on features the cloud tools will
always win (polish at scale, mobile, real-time collaboration). The strategic
opening is everything that is only possible when the model is on the same
machine as the data:

- **It can read everything, not a retrieved sample.** A cloud tool meters
  tokens, so it retrieves five notes and hopes. A local model costs only time,
  so a *slow, thorough* pass over the whole notebook is affordable, overnight,
  or while the laptop charges. `ai/autonomous.py` already has the scheduler for
  this; what is missing is the framing: "MemoryMap read your whole notebook last
  night, here is what it noticed."
- **It can be wrong safely.** Nothing leaves the machine, so a speculative
  suggestion costs nothing but a dismissal. That is why `tensions.py` (finding
  contradictions between notes) is a *better* fit here than anywhere else.
- **It works with no network at all.** Already true and almost never said. The
  `notebook_stats` work in this session is the shape to repeat: a question
  answered exactly, instantly, with the model stopped.

**Action:** the product should say this. An honest, visible "what ran, on what,
and what left this machine (nothing)" surface is worth more than three features.
Some of it exists (`AuditLog`, Settings → Privacy); none of it is a headline.

### 112.2 Missing features, ranked by "would someone pay for this"

Ranked by the gap between what it costs to build and what it would be worth.

1. ~~**Import from other note apps**~~ **Built 2026-10-05** (WORLD_CLASS_PLAN H6 and row 25; HISTORY.md, "Moved from the plans, 2026-10-05 (row 25, the importers and the keyboard)"): `POST /import/app` (`entry/app_import.py`) reads a Notion export (zip, HTML), an Obsidian vault, an Evernote `.enex` and an Apple Notes export, idempotent by source, links as `[[wiki links]]`, front-matter as tags; Markdown folders were built before (`/import/directory`, `/import/markdown`); `tests/test_app_import.py`, `tests/test_vault_import.py`. **Open, small:** attachments are not copied in (Evernote's `en-media` reads as "[attachment]"), and there is no dry-run preview before anything is written.
2. ~~**The nightly pass, as a product surface.**~~ **Built, see `frontend/js/dashboard.js` `renderNightWidget` ("While you were away": each finding opens or dismisses), `api/routes_night.py` and WORLD_CLASS_PLAN I1.** `ai/autonomous.py` exists and
   `tensions.py` exists. What does not exist is the morning artefact: *one card*
   that says what the model did overnight, new links it proposes, contradictions
   it found, notes it thinks are stale, questions it thinks are unanswered, each
   accept/dismissable. This is the single most differentiated thing on this list
   and most of the machinery is already written.
3. ~~**Backlinks on the note itself.**~~ **Built (section 111.2 item 2).** The graph knows what links *to* a note and
   the note never shows it. Half of what people mean by "connected notebook",
   and cheap. (§111.2 item 2, still not done.)
4. ~~**Ask the notebook about itself, generally.**~~ **Built, see `ai/notebook_stats.py` and the agent tools `notebook_overview`, `count_notes` and `notebook_structure` (checked 2026-10-05); new question shapes are added as queries there.** `ai/notebook_stats.py` (this
   session) answers tags/categories/counts/links/timing exactly, with no model.
   The pattern generalises: "which notes have I not touched in a year", "what did
   I write about most in March", "which tags always appear together". Each is a
   query, not a generation, exact, instant, and impossible to hallucinate. **A
   competitor with a cloud model literally cannot make these fast or free.**
5. ~~**Export one note or document** (Markdown/PDF).~~ **Built (section 111.2 item 4).** Backups export everything;
   there is no "send this one to someone". Trivial, and it is the difference
   between a private tool and a tool you can work with other people through.
6. ~~**Typed templates with structured fields**~~ **Built as note types (GRAPH_PLAN KG4).** A category-bound schema
   (decision / owner / due) rendered as a form, queryable afterwards. Tana's
   whole proposition, achievable here because the data is local and the schema
   can be a preference rather than a migration.
7. ~~**A keyboard-shortcut sheet.**~~ **Built (section 111.2 item 7).** `Ctrl+K`, zoom, dictation and the "/" menu all
   exist and nothing lists them anywhere. Ten minutes of work; it is the
   difference between "has shortcuts" and "feels professional".
8. **Per-note pinned AI context**, **Built 2026-10-05**, section 109.4 (HISTORY.md, "backlog-1005"). "Always consider this note", instead of
   hoping retrieval finds it. One preference, one prompt slot.
9. **Highlights as a queryable collection.** **Built 2026-10-05**, section 109.4 (HISTORY.md, "backlog-1005"). `==highlight==` already parses;
   "everything I highlighted this month" is a search-index question.
10. ~~**A conflict-safe editor.**~~ **Built (section 111.2 item 10).** Two windows on one note is last-write-wins.
    Rare, and infuriating exactly once.

### 112.3 Scaling and optimisation, in the order it will actually bite

- **The notes list still has no virtualisation** (§111.1): **Pointer:** section 111.1 above carries the checked state (chunked rendering is built, recycling is not). `renderEntries()`
  rebuilds a node per entry on every keystroke. Fine at 500 notes, unusable at
  50,000, and invisible until someone has the second one. **This is the largest
  scalability item in the app** and the server-side pagination it needs already
  exists.
- ~~**`frontend/js/app.js` is past 30,000 lines.**~~ **Built, see CLAUDE.md section 7 ("`app.js` is 25 files"; chat, the lightbox and the notification centre were the named seams and are separate files now).** The four splits (`library.js`,
  `dashboard.js`, `settings.js`, `documents.js`) worked and stopped. The next
  natural seams are chat (~6k lines), the lightbox (~1.2k) and the notifications
  centre. Each is a session's work and each makes the next bug cheaper to find.
- **Three grammars for markdown** (§111.1): built 2026-10-11, see the entry above (DOCUMENTS_PLAN decision 13).
- **The suite is 2,700 tests and ~8 minutes.** Still fine; worth watching. The
  lints (`test_style_scale`, `test_frontend_ids`, `test_icon_only_buttons`,
  `test_icon_label_gap`) are the cheapest tests in the file and have caught the
  most: that ratio is an argument for more of them, not fewer.
- ~~**Embeddings are optional and the fallback is silent.**~~ **Built, see `frontend/js/capture-ask.js:668` ("keyword search" labels the answer that used no vectors) and `ask-history.js:209` (`search-mode`).** Semantic search
  degrades to keywords with no model; the app should *say* which one answered.
  It is a one-line badge and it is the difference between "the search is bad"
  and "the search is in keyword mode".

### 112.4 What "professionalise" actually means here

Not more features. Four things, in order:

1. **Nothing that is broken.** This session alone found a null dereference that
   silently aborted `openConversation`, a panel that opened five pixels below the
   fold, a checkbox no click could reach, an OCR result thrown away on close, and
   a restore that destroyed the version it was restoring. Every one was invisible
   from reading the code and obvious within a minute of driving the app. **The
   discipline that finds these, reproduce, measure, then fix, is worth more
   than any roadmap item**, and the two new lint files exist to stop that class
   of thing recurring.
2. **One shape for one thing.** Two ⋯ builders drew different glyphs; two Stop
   buttons used different icons; the same setting had two controls that could
   disagree. Each is small; together they are what makes an app feel homemade.
   `test_icon_only_buttons.py` and `test_icon_label_gap.py` are the start of
   mechanising this: more of the design system belongs in lints.
3. ~~**Say what the app is doing.**~~ **Built for the notebook-wide view, see `frontend/js/dashboard.js` `renderActivityWidget` ("what changed in your notebook lately, and whether you, Atlas or a skill changed it") and Settings, Activity.** Background tasks, page reads, captions and the
   nightly pass all now report themselves. The remaining gap is *what the AI
   did*, kept where a person can audit it: the AI edit log is per-document, and
   there is no notebook-wide "what has the model changed" view.
4. **A first run that explains itself.** The onboarding overlay exists. What
   does not exist is the answer to "I have 4,000 notes in Obsidian, now what",
   which is item 1 of §112.2 again, and the reason it stays first.

### 112.5 Deliberately not doing

Written down so a later session does not spend a week rediscovering why.

- **Mobile apps and sync.** The offline, single-machine promise is the product.
  Sync is a distributed-systems project that would compromise it, and the export
  and file-tree work already covers "get my data onto another machine".
- **Real-time collaboration.** Same reason, more so.
- **A plugin marketplace.** The skills library covers reusable prompts; arbitrary
  third-party code in a privacy-first app is a contradiction, not a feature.
- **Chasing Notion's block editor.** Documents has four views and a real
  toolbar. Deciding *whether the note composer converges with it* (§111.3) is
  the open question; rebuilding Notion is not.

## §116: capability gaps identified in the Fable session

Everything here was found while working the plans, by measuring the running
app, by reading a subagent's diff, or by an item a subagent had to drop. Each
line says where it came from so the next session does not re-derive it. Items
already in [PLAN.md](PLAN.md) are referenced by their row id rather than
restated.

### 116.1 Dropped or half-done, and therefore first

5. **Real-model verification of the skills reform**, still the open
   acceptance criterion in AGENT_SKILLS_REFORM.md; needs a machine with a
   4B model, not the sandbox. **(needs owner)**: `scratchpad/llama-dev.sh serve`
   then `pytest -m evals` on a machine that can run one.

### 116.2 Mindmaps, Phases 4-5 (MINDMAP_PLAN.md §5 items 14-21)

(Items 6 to 10 were all built; checked and moved to HISTORY.md 2026-10-04.)

### 116.3 PLAN.md rows not started (by track)

11. **Whiteboard** (PLAN.md rows W1 to W11). ~~W1 group resize, W2 smart connectors, W3 sticky notes, W4 frames, W5, W6's flip keys, W7 undo that survives reload, W8 the minimap, W10 selection export~~ **built** (checked at head 2026-10-05: `wbMultiSelection` group resize, WHITEBOARD_PLAN decisions 14, 18 and 30, `undo-store.js`'s IndexedDB history, `wbNavigator`, `wbSelectionBounds`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)"). **Open, not found built:** W9's palm rejection by `pointerType` (a touch pointer is ignored while a pen draws; only the touch guards exist), and W11's three named selection actions ("Summarise this frame into a note", "Turn these stickies into a mind map", "Explain the connection between A and B"; the AI board tools and "Summarise this branch" are built).
12. ~~**Documents** (PLAN.md rows D4 to D11)~~ **Built** (checked at head 2026-10-05: tables `tests/test_doc_tables.py`, outline drag-to-reorder `docOutlineDragIndex`, callouts and footnotes in `markdown.js`, math `tests/test_doc_math.py`, the revision timeline `tests/test_document_revisions.py`, focus mode (F11) and the dim and typewriter toggles, the AI edit with per-hunk accept (`docAiHunks`, `POST /documents/{id}/ai-edit`); D10 templates exist; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)").
13. **Backend** (PLAN.md rows B1 to B8). ~~B1 the event log (`core/events.py`), B3 errors as a contract, B8 backups as a product feature (`core/backup_bundle.py`)~~ **built.** **Open:** B2's remainder (13 thread modules not yet on `core/jobs.py`, `tests/test_flaw_class_lints.py`'s ratchet), B4/B5's other lists (`/entries` pagination and FTS5 for notes exist), B6's startup check that refuses an unknown schema version, B7's workspace scoping as an explicit dependency.
14. **Harness** (PLAN.md rows A3 to A7). ~~A4 skills as files (`ai/skill_folder.py`, `<data dir>/skills/`), A7's expose half (`mcp_server.py`)~~ **built.** **Open, not re-checked here:** A3's per-line provenance, A5's per-turn budget with a Stop that rolls back partial tool writes, A7's consume half (needs the trust model decided).

### 116.4 Tooling

Both items built (the per-agent launcher is `scratchpad/ui-sweeps/serve.sh`; the
phone and dark runs are in `all.sh`); moved to HISTORY.md 2026-10-04.


## 115. After PR 144: professional use (the owner's stated next block, 2026-09-14)

"After this pr I intend to do a full lot of fixes and refinements for
professional use." WORLD_CLASS_PLAN 18 (H6) holds the gated version;
this is the working list, by what a professional hits first. Each row is
a session or less and names its gate.

| # | Refinement | Gate |
| --- | --- | --- |
| 1 | ~~Import from Obsidian (a vault folder), a Notion export and Apple Notes (HTML), with links and attachments kept~~ **Built 2026-10-05** (`POST /import/app`, `tests/test_app_import.py`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)"); open, small: attachments are not copied in and there is no dry-run preview | a round-trip test per format under `tests/` |
| 2 | **Pointer:** `scratchpad/audit1005/features.md` section 7 (footnotes in print FEAT-03, page setup D4). Print and PDF export of a document with its citations as footnotes | `core/docexport.py` test per format; a printed page has no clipped table |
| 3 | ~~Keyboard-complete: every dock action reachable without a mouse, on every tab~~ **Measured 2026-10-05, nothing to fix:** `scratchpad/ui-sweeps/inv1005-keyreach.js` (140 presses, zero unreachable controls); HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)" | `scratchpad/ui-sweeps/keys.js` extended to every tab, zero unreachable |
| 4 | ~~WCAG AA: contrast, focus order, names on every control, the phone floor~~ **Built 2026-10-05:** the axe sweep (`axe.js`, run by `all.sh` when axe-core is at `AXE_JS`), 0 findings at 1440 light and dark, one rule at 390; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)" | `contrast.js`, `touch.js` and an axe pass clean in both themes |
| 5 | **Next:** `__main__.py` opens one `webview.create_window` per launch; a second needs a route per document or board and the lock state shared, Windows to verify, so the owner's machine. Multi-window on the desktop: a document or a board in its own window | `__main__.py` opens a second webview on a route; state survives a reload |
| 6 | ~~First-run tour that ends in a first note and a first question~~ **Built 2026-10-05:** `scratchpad/ui-sweeps/inv1005-firstrun.js` times it from an empty data folder (the first question no longer pays the embedding model's cold load); HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: BACKLOG)" | time to first answer measured in the tour's own test, under two minutes |
| 7 | **Built apart from the timing gate:** `frontend/js/skills.js:1241-1377` and `tag-manager.js:674` (the Notes selection bar), `library.js` `bulkDelete*`/`bulkMove*` (the Library's own). Bulk operations in the Library: select many, tag, move, export, delete, with undo | a 500-row selection completes in under a second, measured |
| 8 | **Built, see `frontend/js/settings-wiring.js` (`renderSavedSearches`, `persistSavedSearches`, `saveCurrentSearch`: the `saved_searches` preference as chips under the Notes filter, `#saved-searches`) and `tests/test_keyword_search.py` (`test_saved_searches_round_trip`).** Saved searches and smart folders (a query as a sidebar entry) | `search/query.py` round-trips every saved query |
| 9 | **Built, see `frontend/index.html:798` (`#note-template-dialog`, DOCUMENTS_PLAN and CHANGELOG 2026-09-24: built-ins editable) and `BUILTIN_TEMPLATES`.** Templates for notes, not only documents and boards | one recipe shared with the document template chooser |
| 10 | **Built 2026-10-05** (HISTORY.md, "backlog-1005"): `POST /backups/bundle` (zip, or a `.mmenc` sealed with a password) and `POST /backups/bundle/restore`, `core/backup_bundle.py`, Settings, Import & export. Encrypted export and import of the whole notebook (one file, one password) | export, wipe, import, diff equals zero in a test |
| 11 | **Built 2026-10-05**, HISTORY.md ("backlog-1005"): `GET /audit/export.csv` and the Activity chip's Export activity. The activity log as an audit trail a professional can hand over (who, what, when, export CSV) | every event kind exported with its fields |
| 12 | Startup and boot under the speed budget on a five-year-old laptop | `boottime.js` numbers in the CHANGELOG per step |
| 13 | The aurora background's residue (INBOX 210): trails on their own layer redrawn from a short position history, then a pass over the bubbles and mesh styles | `pngpixel.py` reads the ground colour where a ribbon passed two seconds earlier |

Rows 1, 2, 7 and 10 are the ones people ask about before they trust a
notebook with work; do those first.

## Placed from INBOX, 2026-10-03 (INBOX 303, music)

Moved whole from INBOX when INBOX 436 arrived (the tray holds under
twenty). A recommendation awaiting the owner, not open work.

303. **The owner, 2026-09-21, verbatim, with the session's reading beneath
    it:** "it'd be cool if the user can upload songs or connect an in-app
    player to a player or maybe even spotify or youtube music but idk if
    that's offline only anymore...". The local half is a recommendation, not
    a decision, and is in the ANALYSIS.md section named above. The streaming
    half is his: today `routes_settings.py:220` calls web search "The ONE
    feature that goes online, off unless the user opts in",
    `routes_websearch.py:31` says the same in its 403, and
    `dashboard.js:1277` says it to the person, so a Spotify or YouTube Music
    connection would make that sentence false in three places, on top of an
    OAuth flow, a cloud account and a stored token. Recommendation: leave the
    promise absolute and build the local folder player instead; if it is ever
    reopened, it is a second clearly labelled opt-in extra, off by default,
    and the copy in all three places changes in the same commit.

## Placed from INBOX, 2026-10-03 (INBOX 213)

Moved whole from INBOX when INBOX 437 arrived (the tray holds under
twenty); open, by impact with the rest of this file.

213. **Mid-work drop, 2026-09-14 morning, verbatim (the owner), the last
    scan.** "finish all the agents, scan for bugs and high complexity one
    last time, and let me know when the pr is ready to merge / make sure to
    merge all of the agent branches into this one as the agents finish."
    And: "once absolutely everything is done and the roadmap documents are
    cleaned etc, all the agent branches are merged into this one etc, merge
    this pr for me." And (228, the same order, folded in): "after you have
    finished all these, done the final bug sweep, make sure everything is
    finished for the pr, and finish the pr, merging it into main." Owner:
    orchestrator; the merge is the last act.
    **The last scan, run 2026-09-20.** Four passes, each a number rather
    than a reading:
    - **Routes with no caller** (`scratchpad/probe_dead_routes.py`): 320
      served, 9 unnamed by the frontend, every one triaged in 261. Two were
      real and are fixed: `/resurface/near/{entry_id}` was unreachable *and*
      crashed on its first call, and `GET /events` is a built feed with no
      strip to read it (WORLD_CLASS_PLAN B1, still open).
    - **Calls with no route** (`scratchpad/probe_missing_routes.py`, new,
      the mirror and the worse failure): 297 distinct paths called, **0 with
      no route**, both undecidable paths resolved by hand.
    - **Frontend declarations nothing references**: 3,222 top-level names,
      **0** referenced only by their own declaration. No dead weight left in
      `frontend/js/*.js`.
    - **Complexity, backend**, by branch count over 1,827 functions. The top
      five, for whoever takes this on: `_run_one_step` (skill_runner.py:784,
      50 branches / 419 lines), `analyse_attachment` (routes_files.py:381,
      43 / 167), `search` (search/engine.py:645, 41 / 139),
      `_optimization_pass` (autonomous.py:268, 40 / 250), `_run_skill`
      (skill_runner.py:1206, 36 / 300). Not refactored here on purpose: this
      PR is about to merge and restructuring a 419-line agent step is not a
      thing to do on the way out of one.
    **Next:** `_run_one_step` (`ai/skill_runner.py`) is the one worth a spec: split it at its four outcomes (done, failed, parked, retried) with `tests/test_skill_runner*.py` pinning each before the move; the harness agent's file (WORLD_CLASS_PLAN B5), so it waits for that agent's merge.
    A fifth pass, silent exception handlers, was run and is not reported as
    a finding: 251 handlers return a fallback without logging, and in an app
    whose whole design is "degrade to offline" that is the intended shape,
    not a smell. The heuristic could not separate the two, so it is written
    down here rather than left as a number somebody later mistakes for a
    defect count.

## Placed from INBOX, 2026-10-03 (INBOX 266)

Moved whole from INBOX when INBOX 438 arrived (the tray holds under
twenty); open, by impact with the rest of this file.

266. **Mid-work drop, 2026-09-20, verbatim (the owner).** "What usability and
    information architecture things are missing and can be added?? It's often
    the small things that act up, are broken, unreliable, or missing with the
    user needs to work which break the user's trust of the application and
    make it feel less professional, unpolished, like a demo, and not
    trustworthy to be actually used for legitimate work
    Tar file for linus
    Windows msi file
    Version platform architecture for both windows and linux installers
    Lightweight as possible
    what happens if the user runs out of storage??
    needs full backend professional design that accounts for everything
    needs more optimisation
    We need to do a full architecture analysis and make sure that we are
    actually using the right architecture and backend functions. we need to
    make sure that our choices are the best they can be. like why is storing
    in an sqlite database the best way to store notes etc. are things running
    when they arent necessary and taking up extra compute?? things like
    containers are spun up as needed like serverless cloud architecture"
    Open. Seven asks, and most are analysis rather than a fix: (1) the
    usability and IA gaps that cost trust, (2) a `.tar.gz` for Linux, (3) an
    `.msi` for Windows, (4) version, platform and architecture in every
    installer's name, (5) lightweight, (6) what the app does when the disk
    fills, (7) an architecture review with SQLite and idle compute named
    specifically.
    **(6) done 2026-09-21**, measured on a real full filesystem: an 80 MB
    tmpfs mounted as the data dir and filled to 100%, the app driven against
    it. Already right: saving answered 507 with a sentence about disk space,
    and reading, searching and exporting kept working throughout. Three
    things were not. **Unlocking answered 507**, so a full disk locked the
    person out of their own notebook entirely, over the audit row written
    beside it. **A failed backup left a zero-byte file named like a backup**,
    which listed as one, passed `PRAGMA integrity_check` (an empty file is a
    valid empty database) and would have replaced the whole notebook with
    nothing if restored: a full disk turning into total loss through the
    app's own restore button. **A failed upload or export left its
    half-written file behind**, orphaned, holding the space the person was
    short of. All three fixed, plus one ASGI `SpaceGuard` that refuses a
    write bigger than the room left before a byte of it is read, so the app
    can no longer fill the last megabyte and lock itself out. After, on the
    same full tmpfs: unlock 200, reads 200, save 507 naming the folder and
    `0 bytes free`, a 1 MB upload refused up front asking for 3.0 MB, backup
    507 with nothing left behind, every write working again the moment space
    was freed. The 507's sentence now reaches every toast in the app and
    Settings, Data carries a `.notice notice-warn` line when space is low
    (`scratchpad/ui-sweeps/diskspace.js`, PASS in both themes).
    **(7) done 2026-09-21**, both halves. *Idle compute*: with no browser
    attached the server is asleep, 0.04s of CPU across 23 threads in 30
    seconds (0.13% of one core), because every background piece blocks
    rather than polls. The cost is the open tab: two HH:MM clocks ticking
    once a second and a model-status poll asking twice a minute for ever.
    The clocks are scheduled on the wall-clock minute now and the poll
    doubles to a two-minute ceiling while the answer does not change,
    dropping back to 30s on any change, on returning to the tab, on opening
    Settings or on starting a job. Measured with `idle.js` (which now counts
    timer *fires*, not only live intervals) and the new `idlecpu.js`: **timer
    wakes in an idle visible minute 124 to 5, requests 4 to 2, idle CPU
    6.01%/6.11% of one core to 5.50%/5.59%.** Found, not fixed, and a
    decision for the owner rather than an agent: nearly all of what is left
    is the Dashboard's emblem animating at 24fps because it was asked to,
    which the same probe prices at 5.55% on the Dashboard against 2.09%
    parked on Notes. *SQLite*: the answer is written down as a decision in
    `docs/ARCHITECTURE.md` ("Why SQLite holds the notes"), with its reasons,
    its numbers and where it would stop being right, so it does not have to
    be argued a fourth time. No migration started, and the serverless
    question is answered in a paragraph there rather than left hanging.
    **(1) done 2026-09-23**, the usability and IA read against the owner's
    "3 clicks to anything" (INBOX 270): 22 primary tasks driven from a fresh
    dashboard by `scratchpad/ui-sweeps/clicks.js`, 21 within three clicks and
    restoring from the bin at four on purpose (the table is in
    `archive/agent-remaining/guideia.md`). Four trust breakers it found, all fixed:
    both dashboard "Ask" doors opened a disabled Chat box when no model was
    running (now Notes, Ask, which answers without one); the Chat tab never
    said why its box was grey (now the same Connect-a-model line as Ask, the
    agent and the writing desk); a new notebook's Library said "Nothing of
    this kind yet" because the activity log counted as things made (now a
    sentence and a Create button); Create offered no board and no upload
    (now seven rows).
    Checked, not built here (packaging is another agent's): (2) the
    `.tar.gz` ships (`release.yml`, `MemoryMap-AI-<v>-linux-x86_64.tar.gz`);
    (3) the `.msi` steps exist but are `if: false`, so no MSI ships; (4)
    every installer name carries version, platform and arch
    (`installer.iss`: `MemoryMap-AI-Setup-<v>-windows-x86_64`). Still open on
    this entry: (3) and (5).
    **Checked 2026-09-23.** (2) built: `release.yml` ships
    `MemoryMap-AI-<version>-linux-x86_64.tar.gz` beside the zip. (3) built and
    then switched off (`b7b15c7`, WiX v7's fee terms; see 271, resolved). (4)
    built: every artifact name carries version, platform and architecture
    (`MemoryMap-AI-Setup-<version>-windows-x86_64` in `installer.iss`, the
    MSI and both Linux archives in `release.yml`). Left: (1), the usability
    and information-architecture read, and (5), lightweight, whose decided
    shape is lazy imports (268).
    **(5) measured 2026-09-23**, and the lazy-import work is already done
    where it pays. `python -X importtime` over `create_app()`
    (`scratchpad/oi_importtime.py` reads the output): the process imports
    fastapi (402ms), SQLAlchemy (172ms), alembic (129ms) and requests (49ms)
    and nothing heavier; numpy, torch, Pillow, pypdf and python-docx are not
    in `sys.modules` after `create_app`, and peak RSS is 104MB. What makes a
    running server large is the built-in embedding model: 774MB resident on
    a notebook with notes, once `start_warmup` has loaded
    sentence-transformers, and it already waits for the first page, for an
    idle moment and for the notebook to have a note at all. The one lever
    left is which backend embeds, a Settings choice that exists: Ollama's
    `nomic-embed-text` keeps the model out of this process, and the search
    engine's '?' on Settings, Models now says so with the number. So (5) is
    answered; (1) is the one part of this entry left.
    **Status 2026-10-05: all seven asks are answered** ((1) done 2026-09-23 above; (3) the MSI is `if: false` on purpose, INBOX 271 and `b7b15c7`, so nothing is left to build here).

## Placed from INBOX, 2026-10-03 (INBOX 397)

397. **The owner, 2026-09-23 night, verbatim, from the desktop window with a
    screenshot.** "I pressed next on the first panel of the guided tour, and
    it dissappeared while keeping the page dimmed and pushed the top bar down
    by a couple pixels. I begun the tour from the settings help page." and
    "you previously said to me multiple times that you werent able to
    reproduce it, but the bug is real so it has to be something". Read from
    the screenshot: the dim stays on step 1's hole, so step 2 never drew.
    Headless runs from Settings, help at 1333x740, 1440x900, 1600x890 and
    2000x1100 reach "2 of 15" every time, so the cause is in something the
    desktop window has and this sandbox does not. **Guarded 2026-09-23**
    (tour.js): an exception in a step becomes the centred card, a card
    that is off the window or behind something is re-centred, the page's own
    scroll is pinned at 0 before each step (the top bar moving is the
    document scrolling), and each of the three writes a `Tour:` line to
    Settings, Logs. Open until the owner's next run: if it recurs, those
    lines name the cause.
    **Then two more screenshots**, from the welcome's last slide and from
    Settings, help, The basics: the ring the right size and about 620px to
    the right, then 620px to the left, and no card. A shift that flips sign
    is a correction computed from a box read mid-move: `tourPlaceFixed` wrote
    a position, read the element straight back and added the difference, so
    anything that makes the box lag its style doubles the move. Replaced: the
    frame's origin is read from `#tour-origin`, a 0x0 fixed probe nothing
    moves, and the element is read back once a frame later and nudged only if
    it is still elsewhere (with a `Tour:` log line when it is). Headless
    walks of all 15 steps at 1.25x scale, with and without real scrollbars,
    were correct before and after, so the owner's run is the test.

## Placed from the owner's list, 2026-10-10

Entries are the owner's words, then the recommendation. Nothing here has a brief yet.

### Ideas

- "Read all my requests and chat messages sent during and since october 7, analyse them and log them for a new session as I want to start a new one. I also have A LOT of issues and bugs and things Ive written down and ive also tried to get gemini to improve the composer so Ill need oyu in the next session to analyse that open branch as well as the other open branches and fix znd improve everything but I wont send my lists in this session and instead at the start of the next one"
  Recommendation: a process item, not a feature. The next session's first step is to read the owner's chat messages since 2026-10-07 and the owner's lists from that session, log them in the plans, then take the open Gemini branch under Brief 35. Not a brief; the orchestrator owns it.
- "Like this is somewhat a hobby but it is also about ai, local llms and other things."
  Recommendation: context for the scope of the insights and research work, not a request in its own right. Read it with Brief 40 and the insights item in CHAT_PLAN.
- "Is it possible to create custom libraries like the ones vendored that are really good and extensive in their purpose, which can be open sourced and used across projects?? Maybe?? Maybe too much idk."
  Recommendation: a later idea: a small, separately licensed library package built from the vendored engines, after the engine lands under Brief 39. Not scheduled.


## Placed from Brief 40, 2026-10-10 (research and placement)

Each row is a recommendation taken (standing order 3); the evidence is in
[ANALYSIS.md](ANALYSIS.md) "Parity matrix, 2026-10-10" and "Repositories and
libraries read, 2026-10-10".

- **A Docker image.** Recommendation: build it, in two flavours from one
  Dockerfile. Draft at `docker/Dockerfile` and `compose.yaml`
  (not built: the sandbox has no Docker daemon). Measured from a venv of the
  core requirements without `sentence-transformers`: 213 MB of site-packages
  (numpy 70 with its libs, sqlalchemy 28, cryptography 16, uvloop 16), plus
  the app's `src` 28 MB and `frontend` 35 MB (Harper's WASM is 16 of them),
  plus the slim Python base (about 125 MB): about 400 MB on disk, roughly 150
  MB pulled. With `sentence-transformers` and CPU torch (769 MB for torch
  alone in this repository's own venv, 1.5 GB for the whole venv): about 1.6
  GB. Volume layout: `/data` (`TESSELLATE_DATA_DIR`: database, files, the LAN
  certificate, backups) and `/models` (`HF_HOME` and
  `SENTENCE_TRANSFORMERS_HOME`: the embedder, Whisper, RapidOCR, the Pyodide
  and needle downloads), so a notebook reset never re-downloads a model.
  Ollama stays on the host (`OLLAMA_URL=http://host.docker.internal:11434`).
  **Blocker found, three small changes first** (a brief, not a session):
  `__main__.py:32` binds `127.0.0.1` as a constant, and `netbind.bind_host`
  widens it only when the LAN preference is on and a password exists; a
  browser reaching the container through Docker's bridge is "the network",
  and an app with no password answers every network request 403 (SEC-01).
  So the image needs `TESSELLATE_BIND` (default unchanged), a first-password
  environment variable or `--set-password` (today only `--reset-password`
  exists), and a decision on TLS (a reverse proxy in front, with plain http
  inside the compose network). **What the Windows launcher does that a
  container cannot:** the desktop window (pywebview) and tray, the Start menu
  and the Repair shortcut, native file dialogs (`core/desktop_dialog.py`),
  watching a folder on the host, the capture hotkey (`--capture`), OS
  reminders and notifications, the firewall prompt and port search, and
  launching Ollama and detecting a GPU. Everything else (the venv, the
  update check, the health check) a container replaces. Keep for the owner's
  NAS and server users; drop as a desktop install path.
- **Reuse the system Python's packages.** Recommendation: offer it, never
  default it. `start.sh` line 1070 and `start.bat` line 602 run
  `python -m venv .venv`; the choice is `--system-site-packages` on that
  line, chosen only when the installer can import `torch` and
  `sentence_transformers` from the system Python (a saved 770 MB and a
  working CUDA torch if the person has one) and the `--doctor` import check
  passes afterwards; otherwise a clean venv, as now. Risks, in the order they
  bite: (1) a system torch built against numpy 1.x imports the venv's numpy
  2.4 and crashes at import; (2) a broken or half-removed global
  site-packages (a bad `.pth`, a stale `dist-info`) poisons every launch with
  an error that points nowhere near the cause; (3) `pip install -r
  requirements.txt` sees a system package that satisfies the range and
  silently does not install its own, so the app drifts when the system
  package is upgraded; (4) the venv is no longer relocatable when the system
  Python is replaced. Mitigation: record the choice in `.venv/pyvenv.cfg`
  (it is already there as `include-system-site-packages`), print it in
  `--doctor`, and fall back to a clean venv on the first import failure.
- **Does a first install need the internet? Yes, once, and the app says so
  in one place only.** `README.md` (line about "The first launch downloads
  the search model"), `docs/INSTALL.md` (line 130) and
  `docs/TROUBLESHOOTING.md` (line 64) say it about the search model;
  `start.sh` line 1118 prints "Installing, this can take a few minutes" and
  `start.bat` has no equivalent, with no word that it needs a connection;
  the app's onboarding says nothing (no "internet" in `onboarding.js`).
  Measured: the core packages are 213 MB installed, the search model adds
  several hundred MB (more on Windows, where it brings torch). A person on a
  train with a fresh clone gets pip errors that `is_network_error` turns into
  a retry, which is right but late. Recommendation, three edits, one brief:
  (1) the launchers print, before any download, "First start only: this
  installs about 210 MB of packages and needs the internet once. After that
  MemoryMap runs offline."; (2) the same sentence as the first line of
  README "Install" and INSTALL.md "Before you start"; (3) onboarding's model
  step says "Search by meaning needs a one-time download of a few hundred MB.
  Skip it and keyword search still works." with a Skip. The packaged app
  already has the Windows installer page line (`installer.iss` line 218).
- **Parity programme, the next brief per surface** (full tables in
  ANALYSIS.md). Whiteboard: the draw.io reader and shape-library converter,
  connection points, named layers, five templates. Mind map: OPML and
  FreeMind export, branch-by-branch presenting, centrality as a perspective.
  Documents (prose): highlights (Brief 42), a thesaurus from the trimmed
  table, footnotes. Documents (code): completion and the p5 kind (Brief 42),
  editor commands in the palette and a split view, rename within a file.
  Tables: paste-to-table and sort, cell formulas through the safe evaluator,
  chart this table. PDF and OCR: highlights and comments stored in the
  notebook, the encrypted-PDF prompt. Images and Library: EXIF used (date
  taken on the timeline, GPS), rating and flag, crop and rotate. Audio and
  meetings: timestamped transcript with click to seek and SRT or VTT export,
  playback speed, markers. Presentations: speaker notes and a presenter view,
  a per-frame PDF export checked on a real board.
- **Library verdicts to carry into Brief 35's stripping**: drop networkx
  (write the 60 lines `notebook_stats.py` uses), whoosh, pint, langdetect,
  dateutil, pyspellchecker, thefuzz and rapidfuzz (difflib and the trigram
  repair); keep flashtext, rake and the porter stemmer; vaderSentiment only
  where a test shows the gain. Optional downloads, never vendored: Pyodide
  (already), sql.js (new, 700 KB), eslint-linter-browserify (only if Brief 42
  measures a gap). Re-implement small, each with an eval first: bigram
  collocation, tag co-occurrence counting, multinomial Naive Bayes for filing,
  K-means and DBSCAN for merge suggestions, SimHash for near duplicates.
## Expert audit, 2026-10-10

Brief 43. Each row: the probe (command), the number, the cause, the fix shape and the size (S under an hour, M a session, L a plan). Ranked by what a person feels. Measured on a host at load 6 to 14 on four cores, which inflates every time below roughly 2 to 3 times; the ratios between rows and the byte and row counts are exact. Fixed in the audit itself (not rows): a full backup now carries settings; markdown re-import keeps date and pin; the Tidy count (23 s to about 1.4 s, idle server CPU 14.7 percent to 0.3); a safety copy before a migration; select openers named with their value; no 401 on the lock screen; six test modules that could not be collected alone.

| # | Probe and number | Cause | Fix shape | Size |
| --- | --- | --- | --- | --- |
| 1 | `audit-hw.js`, `audit-payload.js` at 5,000 seeded notes: the dashboard is drawn at 4.1 s unthrottled and 6.1 s at 4x CPU (2.2 s on an empty notebook, same host); 25 sequential `GET /entries?limit=200` pages, 3.8 MB, on every unlock | `_loadEntries` (notes-list.js) pages the whole notebook into `allEntries` so search, the sidebar and keyboard navigation work on one array | A windowed list: the first page and counts from the server, the rest on scroll or search; the dashboard widgets that "want the whole of it" (`dashEntries`) ask for their own aggregate endpoints. Re-measure the 2.5 s boot target on a quiet machine first | L |
| 2 | `audit-down.js`, server refused after load: 7 of 7 tabs say "Can't reach MemoryMap. Retrying" (0 blank), but Graph and Library throw `ReferenceError: graphLayout is not defined` and `loadLibrary is not defined` from `switchTab` (navigation.js:1911, 1949) and sit on "Opening the graph…" | The lazy bundle never arrived, and `switchTab` calls its functions unguarded | `switchTab` awaits `ensureModule` and, when it resolves false, draws the `surfaceFailed` notice with Retry in the tab | S |
| 3 | `scratchpad/search-relevance-1010.py`, 60 queries over the showcase notebook (71 notes): hybrid precision at 5 is 0.93, top-1 0.88, any right note in 5 is 0.98; lexical 0.76 / 0.82 / 0.83. Paraphrase top-1 is only 0.68 ("trainers wearing out", "how much did the holiday cost", "quick dinner ideas" put a wrong note first); the typo `pricng` finds nothing relevant (`w_standup`) | No correction offered for a one-letter drop in a six-letter word; paraphrase leans on the meaning signal available here (no embedding model installed) | Typo repair on short words (keyboard-distance already exists in question_noise.py: other agent's file); a paraphrase row set in the evals. Semantic search with a real embedder is not measured | M |
| 4 | The Duplicates review, `entry/tidy.py` via `GET /tidy`: 4.4 to 5.8 s the first time at 5,000 near-identical notes; now cached until the notebook changes | The scan is quadratic in the notebook (already dense-matrix since ARCH-11) | Compute in a background job after a change and serve the last result; or a MinHash prefilter | M |
| 5 | Exports re-imported: markdown now round-trips date and pin; `GET /export/json` has no import route at all; the HTML, docx and PDF round trips are unverified because markitdown, python-docx and a PDF writer are not installed in the sandbox | JSON export was built as a take-away; `POST /import/document` needs the `documents` extra | An "Import a MemoryMap JSON export" door beside Import markdown; run the docx and PDF diff on a machine with the extra | M |
| 6 | Launcher update rollback: `start.sh` self-updates by `git pull --ff-only`; there is no way back to the previous version, and rolled-back code against a newer-stamped database logs "Can't locate revision" and carries on | No release pinning or previous-version record; the safety copy now covers the data only | Record the head before a pull; a `--rollback` flag that checks it out and says which backup to restore | M |
| 7 | Attachments are accepted by extension only (`ATTACHMENT_SUFFIXES`, routes_files.py:94); the media upload at routes_files.py:3483 has a magic-number check, attachments do not | The suffix allowlist predates the sniffing helper | Run the media check on attachments whose suffix claims an image, PDF or archive | S |
| 8 | The vendored engines broke the base branch's gates: `ruff` reports 1,140 errors in `src/tessellate/vendor/` (whoosh, networkx), `test_plan_hygiene` finds a conflict marker at `vendor/networkx/conftest.py:3`, `test_outbound_inventory` finds `vendor/vaderSentiment.py` and `vendor/whoosh/compat.py` able to open connections and unlisted, `test_readme_freshness` says the README's tool count (67) is stale; CodeQL's config does not ignore `vendor/` | Brief 39's vendoring landed without the exclusions the lints and the CodeQL config need | `extend-exclude` vendor in pyproject, `paths-ignore` it in `.github/codeql/codeql-config.yml`, add the two modules to `INVENTORY` as imported and never called, delete the marker, fix the README count | S |
| 9 | `tests/test_chat_intent.py`: `classify("what can you do?")` returns `smalltalk`, not `about_app`; the capability prompt lacks "asking what you can do" (2 failures on the base) | The composer branch's change to intent.py or the composer tables (other agent's files) | Reproduce against `main`, then restore the capability route | S |
| 10 | `axe.js`, light, 1440 px: 7 `label-content-name-mismatch` left after the select fix: `#status-notes`, `#entry-attach-existing`, `button[title="Add this note to a document"]`, `Sort results` (find), `Small model mode`, `Run Embeddings backfill now`, `How Atlas writes its answers`, a heatmap day button (`data-key`) | Icon-and-count buttons whose aria-label drops the visible count or word | Put the visible text first in each aria-label (status.js is another agent's file) | S |
| 11 | `server rss` 285 MB with 5,000 notes after boot and a full list load (target 300); the page heap is 15 MB | The server holds the engines and caches; nothing measured per component | Profile with tracemalloc at 5,000 and 20,000 notes before it crosses 300 | S |
| 12 | `GET /graph?slim=1` is 1.2 MB at 5,000 notes and is fetched twice per boot (`audit-payload.js`); the graph worker's frame time at 2,000 nodes was not measured (no linked fixture; graph*.js is another agent's) | The payload carries every node | Cap or tile the slim payload; run `gwperf.js` with `scratchpad/graph-fixture.js 2000` | M |
| 13 | `python -m alembic upgrade head` on an empty file fails at the bookmarks migration (`NoSuchTableError: bookmarks`) | The table is born by `create_all()` after the baseline, so the chain only works behind `DatabaseManager`; `tests/test_alembic_full_chain.py` pins the supported path | Create the table in a migration, or document that Alembic is only run by the app | S |
| 14 | `tests/test_learned_spec.py` and `tests/test_resurface_spec.py` still say "Strict-xfail until built", and CLAUDE.md section 7 says the specs are strict-xfail; `grep xfail tests/` finds no marker, and all 63 spec tests pass | The markers were removed as the features landed; the sentences were not | Reword the two docstrings and the CLAUDE.md paragraph | S |
| 15 | Process: `git stash` is shared by every worktree. Two agents popped each other's stash in this audit (a packaging agent's 13 files appeared in this worktree) | A worktree's `git stash pop` takes whatever is on top | Add "never `git stash`; commit a WIP instead" to `scratchpad/AGENT_COMMON.md` and the brief protocol | S |

Passed with a number, no row needed: the frontend lint set, three serial runs of 429 tests, 51 to 58 s each, no flake; `--durations=20` over the 17 `test_api*` and `test_chat*` files, 192 tests in 103 s serial, slowest 2.4 s; `fe1005-offline.js`, seven tabs in a French locale, zero requests to any other origin; the service worker has no `fetch` handler and caches nothing, stamped assets are `public, max-age=31536000, immutable`, the shell is `no-cache`; `keyboard.js`, `dockeyboard.js` and `errors.js` at four widths, zero findings; `a11yname.js`, zero unnamed controls; the router-walk test `tests/test_every_route_is_locked.py` already exists and passes (every route answers 401 to a stranger, an allowlist of 18 open paths with reasons); the unlock throttle exists with tests; the app's CSP has no `unsafe-inline` (the sandboxed Run pages keep theirs by design, on an opaque origin); CodeQL runs on every push and PR plus Mondays, `security-and-quality` queries, Python only, `.github/workflows/codeql.yml`; `autogrowfast.js` 3 of 3, 0 mismatches. The 0.3.0 schema itself cannot be rebuilt (history was squashed at 0.4.1); the baseline revision to head with data in place is the earliest testable chain.

- **Live refresh across devices** (INBOX 881, the owner 2026-10-11: "what if I make a change on my phone?? does it live update??"). A save on one device does not refresh another device's open list or note. Recommendation: an `entries` event on the existing jobs stream; the list re-fetches, and an open note that has no unsaved edits takes the new text, while one with edits keeps the 409 Keep mine / theirs prompt.


## Placed from INBOX, 2026-10-12 (grammar in digest answers)

- INBOX 1299. **The owner, 2026-10-12, verbatim.** "this response from the ask subtab
     is great! i would make a small tweak or two like it probably should have
     said instead \"A week on, by 9 August, you mentioned that you had just
     recently begun playing League of Legends...\" small grammar issues like
     that ... can we use the vendored grammar repos like harper to improve
     composer responses?? maybe that cna be fore next pr". Fixed now: "every a
     week", "Your the split ... note". Next PR (recommendation, taken): a
     dated digest line after "A week on, by D," reports in the past ("you
     mentioned that you had ..."), and the vendored Harper rules run over
     composer output as a test-time lint first, then as a post-pass on lead
     capitals ("tuesday") and missing articles ("go to gym").

## Start of the next PR (the owner, 2026-10-12, "log everything I've mentioned")

First, in order:
- The 17 seeded `composer_digest.py` rows are split and deleted (composer-1018b). Left of INBOX 1298: the 18 seeded functions that grew (`_stream_lines` 93 to 106, `_generate_diagram` 27 to 47, `mcp_server.handle_request` 17 to 30 and 15 more whose first seed values were not recorded; `python scripts/complexity.py`).
- Settings: the '?' help button in a section header sits mid-row; it belongs right-aligned with a token gap, left of "Reset N changes". No gap between a select ("5 minutes") and its per-row reset button.
- Activity card: the Logs button wraps to its own row; pin it top-right (absolute) so the title never moves it.
- OCR workspace through the "m o" chord opens with nothing selected and a blank viewer: select the first file, and when the page renderer package is missing say so with a link to Settings, Packages.
- Packages: Live captions (whisper.cpp) has no install control; if it is not wired yet, show it disabled like llama.cpp.
- Ask without the needle package: say so in a notice naming what it adds, never a quietly poorer answer; answer the owner's question of whether the composer needs it to call tools or only to retrieve.
- Composer: past-tense reported speech and the Harper test-time lint are built (`tests/test_composer_grammar.py`); the post-pass for lead capitals and missing articles is `composer_digest.polish` (closed lists). Left: a Harper suggestion UI in plain boxes (cite-1018 "Left from step 2").
- The agent cap: the owner cannot fund two Opus agents at once right now; run one at a time, Sonnet for named fixes.
- Companion physics: when the companion falls it is glitchy and choppy, about 4 frames a second (owner, 2026-10-12). Measure the fall loop's frame times first (`companion-motion` tests, `avatars.js`), then fix the step rate. Owner again 2026-10-17 (bugs-1017 B87a): throwing a companion is "insanely framey and laggy and not clean"; still never measured.
- Chord key: "s" is Settings (`CHORD_ACTIONS.s`), so "View the Stack" on "s" collides; pick a free letter.
- Rename leftovers, only if the owner asks: release asset names (`ASSET_PREFIX = "MemoryMap-AI-Setup-"`, routes_update.py), the exe "MemoryMap AI.exe" and the Start-menu ID, each with a migration. <!-- brand: keep -->
- Unverified on Windows: the launcher splash (title lockup, centred links, `scripts/splash.ps1`; pwsh is not available here).
- Graph load: it does not appear smoothly, it shifts or glitches in (owner, 2026-10-12). Record frames across the first second (node positions per frame, `graph-worker.js` settle, the canvas resize) and fade in once the layout has settled.
- Mind map: with a popup tool panel showing, a two-finger trackpad pan is slow and laggy (owner, 2026-10-12). Likely the panel's blurred surface repainting under the moving canvas (DESIGN.md glass-off list) or a wheel handler doing layout work per event; measure frame times with and without the panel before fixing.
- Atlas's head tilts toward the mouse like the other companions when that setting is on (owner, 2026-10-12; the Settings persona card shows the head only). Check the companion's look-at path covers the persona head and the chat avatar.
- Composer without a model (owner, 2026-10-12 screenshots): (1) "search the web for sandwiches" with Web on answered "No note I found says anything about search or web or sandwiches" (the 2026-10-12 `asks_web` fix is in the head; re-test it first, the owner may be on an older build, then add a "Web is on but no search engine is set up" line when it still cannot search); (2) "what is the time right now" answers 18:53, with no am/pm option: read the clock format setting and say "6:53 pm"; (3) "what about the time in japan??" fell to notes: a follow-up must inherit the last turn's subject (time) and a place maps to a time zone (offline table); (4) no simple conversions (units, currency needs a rate so say so, time zones) and no conversation context across turns: add a `conversions` act in `ai/composer_acts` and carry the previous act and slots into a terse follow-up. These belong with CHAT_PLAN's deterministic engine, Brief 90 (the owner's typos are fixtures).
- Chat "can you search the web?" with Web on: the Atlas bubble stays empty and the person is told to look at the logs, which are not human readable (owner, 2026-10-12). Every failed turn must end in a plain sentence naming what failed (no search engine set up, offline, model off) and the next step, never a blank bubble; and the Logs view needs a readable line for the failure. A "search up sandwich recipes" turn answered "I found 11 notes about up sandwich recipes" from notes: the verb "search up" is not read as a web ask (`_WEB_ASK` in composer_digest.py), and the leading "up" stays in the query.
- Atlas and the companion need a refinement pass (owner, 2026-10-12): Atlas's right arm still looks disconnected from the body, arm movement is odd, some popup icons and actions are not animated (the juggling stars among them), and behaviour, motion and actions want more refinement and optimisation. Measure the arm joint against the torso per pose first (the crop shows the arm detached at the shoulder), then audit which popup actions have no animation. Owner 2026-10-17 (B87c): the companion needs much better behaviour, actions and lifelike decision making; Opus brief after the composer agent. 2026-10-17 (`companion-mind-1017.md`): the juggling stars, the decisions, transitions and three new acts are built (b3d2971, 06797e5); 2026-10-18 (`companion-1018.md`): the popup-actions audit is done (every menu row answers with a move or an act; "Stay here on every page" alone showed nothing and now nods), and the arm joint is measured, not fixed: the shoulder's cut line lies 0.3 to 0.9 drawing units (about 0.3 to 0.9 px at the companion's size) outside the torso fill in some poses and acts, on both arms alike (right 0.85, left 0.88 in the same states; `scratchpad/ui-sweeps/armjoint.js`, feminine hanging, sitting and idle variants clean at 0 to 0.28), and the pixels there at 4x are not background (`armpixels.js`: 216 to 247 against 255), so there is no right-only gap to fix; open only if the owner shows a crop that a number can match.
- Timer (Statistics): the "Breaks" toggle and its label are not vertically aligned, and the preset row (5, 15, 25, 50) and the minus, "25 min", plus stepper may belong on separate rows (owner, 2026-10-12, screenshots); measure the toggle and label centres, then split the rows at narrow widths at least. Measured 2026-10-17 (the Focus timer widget, 1440 and 390): the Breaks label text centre, the Start and Reset buttons and the row all sit within 0.2 px of each other (checkbox 1 px above); the preset row is one row at 306 px (segments 174 + stepper 106). Not reproduced; ask the owner for the width and look.
- One loading screen for every main page (owner, 2026-10-12: likes the bar-at-top "Opening documents" ring with skeleton pieces; wants it, with the sheen moving, on the others). Checked: `TAB_SKELETONS` (navigation.js) holds graph, library and documents only, because it covers a lazy tab's module load (`tabPlaceholder`; `tests/test_lazy_skeletons_598.py` requires one per lazy tab). Dashboard, Notes, Chat, Timeline and Reminders are boot-loaded, so their wait is a data fetch drawn by ad hoc skeletons (`showSkeletons`, `dashFillingSkeleton`, the calendar's `timeline-cal-loading`). Do: a `surfaceLoading(page, spec)` that reuses `tabSkeletonDock` and the ring line for any data wait past 400 ms, a spec each for dashboard, notes, chat, timeline (list and calendar), reminders, whiteboard and mind map, and check the sheen runs on every `.skeleton` (the reduced-motion breathe stays).
- "Atlas, needle3" turns (owner, 2026-10-12: "all the needle stuff isnt working"): the tool-calling path labelled needle3 answered "What did I write this week?" with a counted-notes step and "You have no notes in this week" (correct on a Monday, but the answer should say the week it read, Monday to today, and offer last week). Check each needle-labelled step (count, search, open) against a real model and report what the label means in the UI; an unreadable model label is a bug in itself.
- Missing packages (owner, 2026-10-12): wherever a feature needs a package that is not installed (viewing a PDF or other files, the needle tool-calling model, live captions, OCR), say so at the point of use with a short notice or a bell entry naming what it adds and a button to Settings, Packages; one shared helper (`capability` flags in routes_capabilities.py) so each surface asks the same question, and a lint that every gated control has its notice.
- Composer understanding: fold every typo and phrasing the owner has used in this conversation into the fixtures (Brief 90: "tuesday" lead capitals, "bototm", "dissconnected", "wierd", "Cristopher", "gamin", "mouce", "search up", "what about the time in japan??", "hey :D", "can u pls") and generalise the classes (one-edit keyboard slips, dropped or doubled letters, missing apostrophes, trailing "??", emoticons, "u", "pls"), then widen what it understands: follow-up turns that inherit the last act and slot, time zones and 12-hour clocks, unit conversions, a web ask with no engine set up.
- Backspace and delete are laggy in the editor (owner, 2026-10-12): profile the input path (the autocorrect and spelling passes on each keystroke, `tag-suggest`, the markdown preview repaint) with a long note and debounce what runs per key.
- Search history panel (owner, 2026-10-12, "maybe next PR"): a panel of recent searches (Find anything, Ask, library) with re-run and clear, local only; the palette already keeps recents, start from there.
- Guide answers "what can I do in the chat?? like what should I ask for??" (owner, 2026-10-12, screenshot: not good enough): it restates the question ("Taking that as ..."), then describes the "/" menu, when the person asked for ideas. For a "what should I ask / what can I do" question the Guide should answer with three to five concrete example questions for that surface (Chat: "What did I write this week?", "Summarise my notes in Hobbies", "What is due soon?", "Find notes about X", "Remind me to ... tomorrow"), each a tappable chip that fills the box, then one line on the "/" menu. Drop the "Taking that as" echo when the question was understood (it only helps on a low-confidence parse), and read "cna" and a trailing "??" as noise. Also give Chat's own empty page the same chips.
- Dashboard default layout (owner, 2026-10-12): improve `DASH_DEFAULT_SHOWN` and `DASH_DEFAULT_WIDE` (dashboard.js ~139 to 190) using the owner's own order as the model (Digest, Notebook constellation, Quick capture, Recently added, Most used, Top tags, Recent questions, Tag cloud, Rediscover, Activity heatmap, Categories, Most-linked, Focus timer, Favourites, Reminders, Loose ends, Boards and maps, Recent documents, Writing pace, Tensions, Unfinished, Recent activity, While you were away, Bookmarks, Stats, Streak, Most opened this month, Filings to check, then This week and On this day). Only the constellation starts wide in the owner's layout; every widget that starts wide must have a working Narrow button in the Widgets sheet (the heatmap's did not once), so add a test that toggles every `DASH_DEFAULT_WIDE` widget to narrow and back.
- Clock (owner, 2026-10-12): an Appearance setting for 12 or 24 hour time for the status bar clock, the dashboard and reminders clocks and Atlas's time answer (`utilities._hm`, which already speaks 12-hour on request), and a switch to turn the composer's clock answer off.
- Splash (owner, 2026-10-12): the expanded log now sits under the step list (`scripts/splash.ps1` `Set-Layout`); not run on Windows from here. The log box's scrollbar is the system's white one against the dark card; a dark custom scrollbar needs a RichTextBox or an owner-drawn bar.
- Hugging Face token (owner, 2026-10-12): Settings, Models (where models are pulled) and Search and index each get a section with a text field and a button for a Hugging Face access token, stored securely (the OS keychain where one exists, else the encrypted settings store; never in plain text, never logged, never in exports or backups), shown masked, and manageable: add, update, edit, delete, with a "Saved" state and a test button that checks it against the Hub without leaving the machine otherwise. Gated downloads (private or licence-gated repos) and the embedding model pull read it; a lint that no route returns it.


- A full lag sweep and optimisation pass (owner, 2026-10-12): collapsing and uncollapsing notes in the list is glitchy and laggy, and many actions across the app feel slow. Measure first: record frame times and long tasks (PerformanceObserver `longtask`, `event` timing for INP) for the note list collapse, tab switches, the editor keystroke path, graph and mind map pan with a panel open, and dashboard load; rank by cost; fix the worst ten (layout thrash from per-note height reads, backdrop blur on moving surfaces, per-keystroke passes, animation on width and height), each with a before and after number and a ratchet test.
\n
- Whiteboard template zones (owner, 2026-10-12, screenshots: a "Cues" zone with sub-writing "Questions and key words"): double-clicking the sub-writing to edit it replaced its text with the zone's title ("Cues"), clicking off kept the change, and Undo did not bring the words back. Three faults: the edit box opens on the wrong string (the title, not the subtitle), the commit is not an undo step, and the commit saved the wrong field. Reproduce on a Cornell-style template zone first; the commit must push one undo entry with the field it edited.
- Mind map pan lag with a node selected and its floating toolbar showing (owner, 2026-10-12, third report, "soooo incredibly laggy"): with a node selected the pan is slow. Profile it before touching it: pan with nothing selected, with a selected node and no toolbar, and with the toolbar; check whether the toolbar repositions through layout reads on every pan frame (`getBoundingClientRect` per pointermove), whether the selection ring redraws the whole SVG, and whether the toolbar's blur is on a moving surface (glass-off list). Fix: position the toolbar with a transform from cached geometry, throttle to one write per frame.
- Image and sketch processing indicator (owner, 2026-10-12, screenshots of a sketch tile and its lightbox): nothing on the image itself says OCR or captioning is running for it. Add a small "Reading" or "Captioning" chip with a ring on the Library tile, the Notes attachment chip, the sketch card and the lightbox while its job runs (the jobs stream already carries the target id; `/jobs/stream` `runs`), then a quiet "Read" tick when it finishes, and the same skeleton sheen on the caption line until the words arrive.
- Image lightbox details box (same screenshots): the "820 x 480 . Added ... . sketch-....png" box sits low over the page behind it with a rule inside and a dead strip under it, and the toolbar overlaps the Library tiles behind the lightbox. Give the details a proper bar attached to the viewer (one line, no inner rule) and a scrim that covers the page.
- UI freezes while OCR and captioning start (owner, 2026-10-12): after uploading a sketch as a note, the Notes tab was glitchy for about ten seconds and the view-mode dropdown would not open until the OCR and caption jobs appeared in the agent popup. Something on the main thread or the event loop blocks while those jobs spin up: suspects are a synchronous model or engine load on the request thread (the caption model, the OCR engine import), the jobs stream replaying a large batch into `renderTasks`, or the server's single worker holding the first poll. Measure with a long-task observer and the server's request times during an upload; start jobs off the request path (a thread or process) and show the processing chip at once so the wait is visible.
- Captioning and vision OCR when the model server is down (owner, 2026-10-12, logs and the bell): the log was a page of traceback for a plain refused connection (now one line: `captioning.server_unreachable`); the bell said "Failed: Captioning" but "Finished: Reading an image with the vision model" for a vision read that also failed, so the job must end failed when `vision_ocr_text` returns None because the server was down. Both should say in plain words "Ollama is not running: start it and press Read again", with a button on the image's chip, and a retry that runs by itself when the model comes back.

## The 2026-10-12 sweep: everything said and not done, so nothing is missed

Owner's list, in one place (each is also logged above where it has detail):
- **Rename, finished this session:** release assets, the installer, the bundle folder and exe are now Tessellate (`Tessellate-Setup-*`, `Tessellate.exe`, `tessellate.spec`); existing users uninstall and reinstall. Left on purpose: the data-folder fallback (`%APPDATA%\MemoryMap AI` is read while it exists, so notes are not lost), `instance_lock.APP_NAMES`, the old-name help keywords, old shortcut cleanup in `start.*` and `uninstall.*`, the `memorymap` command alias, the LAN cert subject, browser storage keys, file-format ids. Check the first release builds an installer named `Tessellate-Setup-<version>`, and that the upgrade check in package-check.yml starts running once a release carries that name.
- **README:** tagline options 1, 4 and 5 liked but "not quite right" (owner, 2026-10-12): write two more variants mixing them; the bold line is in README.md, docs/index.html and the repo description.
- **Tool-call answers (needle and the composer):** an answer should state the tool result in words (the counts, the titles, the dates) and never send the reader to the steps to find it ("I found 11 notes about ... Open one from the rows below", "Finished 1 step"). Rule: every `tool_say` result carries its own sentence of findings plus the next action; add a test that no answer says "see the steps" or "below" without naming what is below.
- **Still open from earlier this session, all in this file:** the lag sweep; Hugging Face token; processing indicator on images and sketches; lightbox details bar; UI freeze while OCR and captioning start; captioning and vision OCR failing when the server is down (job must end failed, plain notice); template zone edit and undo; mind map pan lag with a toolbar; Atlas and the companion refinement and the fall physics; composer: web search with no engine, follow-ups and context, conversions, am/pm and time zones, Harper grammar, the typo fixtures; popup agent in-text citations; Guide answers "what should I ask"; missing-package notices (whisper.cpp install, needle, PDF viewing); search history panel; 12/24 hour clock setting; chord key "t" and "s"; graph load fade tuning; the CodeQL alerts if any return; the full local suite was not completed.
- **Not verified this session:** the Windows splash changes, the installer build after the rename, every UI change beyond the measured ones, the full local suite.

- Composer quality outside Ask (owner, 2026-10-12): the composer is great in the Ask subtab and decent in the Guide, but sub par in Chat and in the needle (tool-calling) path, for web searches, specific questions about notes and how-to questions. Bring Chat to Ask's answer engine: route Chat's no-model turns through the same digest path, state tool results in words (see "Tool-call answers" above), and give how-to questions the Guide's topic lookup. Measure first with a fixture set of real Chat questions run through Ask, Guide and Chat side by side.
- Slash commands in Chat and the composer (owner, 2026-10-12; idea from Compass's DETERMINISTIC_COMMANDS.md): `/` commands that run exact, model-free queries and answer in a bubble. One registry feeds the commands, `/help <command>` and the `/` autocomplete, so they cannot drift. Start: `/recent [n]`, `/count [tag or category]`, `/stats` (notes per category and week, streak, last note), `/tags`, `/due`, `/find <text>` (FTS5), `/time [place]`, `/open <note>`, `/help`. More (owner, 2026-10-12): `/calc <expression>` (exact arithmetic, units and percentages, through the existing `calculate` tool); `/made <date or range>` and `/edited <date or range>` (notes, boards, maps and documents created or changed on a day, "last week", "since 3 Oct"); `/list <type> [type ...]` (every object of one or several types: notes, documents, boards, maps, reminders, meetings, files); `/with <word or "phrase"> [in <type>]` (objects whose text contains the word or phrase, with the matching line shown); combinable, for example `/list notes documents edited last week with "invoice"`. Each answers as a sentence plus an interactive list (open, jump to the match), per the readable-results rule. Further candidates (owner asked, 2026-10-12), highest value first: `/today`, `/due [today|week]`, `/calc`, `/with`, `/stats`, `/untagged`, `/orphans`, `/random [type]`. Then retrieve (`/yesterday`, `/uncategorised`, `/linked <note>`, `/similar <note>`, `/duplicates`, `/long`, `/short`, `/pinned`), statistics (`/words [period]`, `/streak`, `/busiest`, `/top tags`, `/top categories`, `/growth`, `/storage`, `/compare <period> <period>`), time (`/overdue`, `/remind <text> <when>`, `/done <n>`, `/agenda`, `/countdown <date>`, `/age <note>`, `/date +30d`, `/weekday <date>`), calculation (`/convert 5 km to mi`, `/percent 15 of 80`, `/tip`, `/split`, `/sum` `/avg` `/min` `/max` over numbers in a tagged note), edits (`/new`, `/append <note> <text>`, `/tag`, `/move`, `/undo`, `/redo`; `/delete` and `/merge` keep their confirm step) and app (`/go <place>`, `/theme dark|light`, `/backup now`, `/export <type>`, `/skills`, `/status`, `/help <command>`). A missing argument returns a usage hint. Hybrid commands may add an optional AI summary after the exact result; every command works with no model. Help moves with the UI (standing order 13). Place the brief row in CHAT_PLAN.
- Tool results are always readable (owner, 2026-10-12, scope widened the same day to every needle tool call, web search, `read_url`, file and document reads, the `/` commands and failures such as no search engine set up or the model off): every tool result reaches the chat bubble as plain sentences or an interactive panel (rows, cards, chips), never raw data. `tests/test_tool_say_coverage.py` holds the floor (every tool has a sayer; empty and failed results say a sentence). Next: a test per tool of a realistic result that checks the answer names the counts, titles or dates.
- Natural Language Tools (arXiv 2510.14453, unverified for small models): letting the model name a tool in words instead of JSON may raise the needle's tool-calling accuracy; measure on the local model before adopting.
- Composer direction for the next PR (owner, 2026-10-12): the composer takes `/` commands and also repairs the user's input. A mistyped command or a wrong argument is called out in a plain sentence, with the nearest alternatives as tappable chips ("There is no /recnt. Did you mean /recent?") and, when one reading is clearly right, the inferred one is run and said so ("Read as /recent 5."). Same for typos and unclear natural phrasing: infer, say what was inferred, offer the alternatives, never fail silently. The role: with a model on, the composer is the assistant and boost to it everywhere in the app (it answers what it can exactly, and hands the model exact facts, dates, counts and note excerpts to ground its reply); with no model it is a complete replacement that is just as good, never a lesser mode. Measure that claim with a side-by-side fixture set (the same questions with the model on and off) before saying it is met.
- Command palette above the chat input (owner, 2026-10-12): typing `/` opens a small popup above the text bar, built from the same command registry as the commands and `/help`. It shows the closest commands as you type (fuzzy, so a typo still finds `/recent`), each row with its name, a one-line description and its structure (`/recent [n]`, `/made <date or range>`); Up and Down scroll, Enter or a tap fills the bar with the command and leaves the cursor on the first argument; Tab completes. Once a command is chosen the popup becomes its argument helper: argument names, example values, prefilled choices as chips (types, dates such as today and last week, your tags and categories, recent notes), and a live preview of how the composer reads it. Recently used commands come first; an empty `/` shows the groups (find, time, stats, edit, app). Built from DESIGN.md's recipes (the popup like the existing mention and suggest menus, `data-help-for` help, tokens for spacing), keyboard and touch complete, closes on Escape or a click away, never covers the send button, and works with no model. The registry and the popup cover every command named in the slash-command entries above, the first set and the further candidates (`/calc`, `/made`, `/edited`, `/list`, `/with`, `/today`, `/due`, `/stats`, `/untagged`, `/orphans`, `/random`, `/convert`, `/remind`, `/go`, `/theme`, `/backup` and the rest), each with its structure, an example and its argument chips. The aim is learnability: a person should discover every command, and its shape, without reading help.
- Composer: natural language equals slash commands, and richer answers (owner, 2026-10-12): the composer must be able to do anything a `/` command does and infer the command from ordinary language ("what did I write last week" runs `/made last week`; "any untagged notes?" runs `/untagged`; "how much did I spend, from my expenses note" runs `/sum`). One registry means one set of actions with two entrances, the typed command and the inferred phrase; a phrase that could mean several commands offers them as chips and says which it picked. Answer shape: the reply may be a natural-language answer of a couple of paragraphs with the tool results set in the middle (the lead sentence, then the results as rows, cards or a table, then a closing line that interprets them and offers the next step), and a question that needs several tools (for example notes about a trip, the reminders due before it and the days left) runs them in order, shows each result in its own panel and ties them together in the prose. It must work with no model (rule-built prose from the results) and, with a model, hand the model the exact results to phrase. Judge it on a fixture set of multi-part questions, checking that every number, title and date in the prose appears in a tool result (the existing source check), before calling it smart.
- Creation commands (owner, 2026-10-12): `/` commands that make new objects, each also reachable by natural language ("make me a mind map about the trip"). Notes: `/new <text>` (first line becomes the title), `/note <title>: <body>`, `/quick <text>` (straight into the inbox), `/journal` (today's entry, created once and reopened), `/daily`, `/idea <text>`, `/todo <text>` (a checklist note), `/list <title>: a, b, c` (a checklist from items), `/meeting <title>`, `/template <name>` (a note from a saved template), `/clip <url>` (a web page note), `/dictate`. Other objects: `/doc <title>` (document), `/sheet <title>` (spreadsheet), `/board <title>` (whiteboard), `/map <title>` (mind map), `/remind <text> <when>`, `/event <title> <when>` (timeline), `/category <name>`, `/tag <note> <tag>`, `/link <note> <note>`, `/skill <name>`, `/folder <name>`. Every creation answers with the new object as a clickable card ("Created the note “Pack list”"), is undoable with `/undo`, accepts `in <category>` and `tagged <tag>` suffixes (`/new buy milk in Errands tagged home`), and a missing title or a duplicate name gets a plain sentence with the closest alternatives instead of a silent failure. The same registry feeds the popup, so each shows its structure and an example as you type.
- More slash command candidates (owner: "and more if you can think of any", 2026-10-12), all model-free and answered as a sentence plus an interactive list: `/starred`, `/pin <note>`, `/unpin`, `/star <note>`; time windows `/thisweek`, `/lastweek`, `/month`, `/oldest [n]`, `/onthisday` (notes from this date in past years), `/changed since <date>`; detected things `/todo` (open checkboxes across all notes), `/questions` (lines ending in a question mark), `/links` and `/urls` (notes containing links), `/images`, `/files`, `/people` and `/mentions <name>`, `/places`, `/dates` (notes that name a date), `/quotes`; per note `/tags <note>`, `/wordcount <note>`, `/readtime <note>`, `/versions <note>`, `/diff <note> <note>`; digests `/summary <period>` (a rule-built recap of a day, week or month), `/digest`; organising `/categories`, `/rename tag <old> <new>`, `/merge tags <a> <b>`, `/templates`, `/meeting <title>`, `/journal`; surfaces `/mindmap <note>`, `/graph <note>`, `/board <name>`, `/bin`, `/restore <note>`, `/history` (chat and search); utilities `/timer <minutes>`, `/focus 25`, `/stopwatch`, `/roll 2d6`, `/flip`, `/pick a, b, c`, `/random number <a> <b>`; app `/models`, `/web on|off`, `/lock`, `/shortcuts`, `/version`, `/about`. All join the one registry and the popup; a command that changes data (`/rename`, `/merge`, `/restore`, `/pin`) shows what it will do first and is undoable.
- Bare commands guide the user (owner, 2026-10-12): a command typed with no arguments never fails or guesses; it opens its own guide. `/new` with nothing opens the new-note composer (or a small form: title, category, tags); `/remind` opens the reminder form; `/made` or `/edited` with no date opens a date picker with today, yesterday, this week and last week as chips; `/list` opens a type picker (checkboxes for notes, documents, boards, maps, reminders); `/with` asks for the word and the types; `/convert` and `/calc` show a short example and a keypad of units; `/go` offers the places as buttons; `/theme` and `/backup` show their choices. Each guide is a small panel in the chat (or the popup above the input), step by step when the command has several arguments ("Which type? Which period? Which word?"), with the answers filling the command line as it goes so the person learns the typed form, a back step and a cancel. Commands that navigate (`/go`, `/graph`, `/mindmap`) take the person straight to the place. The popup and the guides read the same registry, so a new command gets both for free: its argument list says whether each argument is a date, a type, a note, a tag, text or a choice, and which control asks for it.
- Quick command bar from anywhere (owner, 2026-10-12): a small popup text bar for running quick commands, opened from any screen, linked to the existing command palette (`openPalette()`, Ctrl+K). Plan: the palette gains a command mode. Typing `/` in the palette (or a dedicated shortcut, for example Ctrl+/ , plus a button in the dock) turns it into the quick bar: one line, the same registry-driven suggestions above it (the command popup in the chat input), the same guides for a bare command, and the result shown right under the bar as the same readable bubble or panel, with "Open in chat" to continue it there. Results that change data show what they did with an Undo. It stays open for a follow-up command, closes on Escape or a click away, remembers recent commands, and works with no model. One command engine serves the chat input, the palette and the quick bar, so a command behaves the same in all three. Reuse the palette's existing dialog and the suggest-menu recipe in DESIGN.md; a global shortcut needs an entry in the shortcuts list and its help topic (standing order 13). Note what exists first: grep `openPalette` and the palette's own search before building.
- Frame-cost sweep (owner asked, 2026-10-12, after the mind map selection bar was found placing itself in 30 ms a frame during a pan; fixed with a held measure, `tests/test_wb_pan_bar_hold.py`): the same class, something that follows the canvas or the pointer and re-measures each frame, may live elsewhere. Method: for each surface (board, graph, mind map with every bar and strip, documents toolbar, timeline, the companion and Atlas during a throw), select something, then pan, zoom or drag at a 6x CPU throttle and record per-frame time and `getBoundingClientRect` counts; anything over a few ms a frame is a candidate. Checked so far with nothing found by reading: the graph zoom handlers and the editor's `selectionBarSync`.
- Companion and Atlas throw is laggy and framey (owner, 2026-10-12): profile first (a throw at a 6x throttle, frame times, long tasks, what runs per frame: the physics step, the SVG or DOM writes, a blurred layer under the moving sprite, layout reads), then fix the biggest; likely the same shape as the bar (reads after writes each frame) or per-frame style writes to many nodes.
- Type tolerance everywhere (owner, 2026-10-12: "its just type tolerant in general. the composer should be tolerant of everything and use all the libraries and stuff to handle them, and that should be used to help with the searches and tools and commands"): "can u pls serch teh web for sandwiches" failed because one word ("serch") was missing from the speller's dictionary, patched by hand on 2026-10-12 (`question_noise.SLANG`: serch, serach, saerch, wbe). The repair machinery already exists (`question_noise.repair`: weighted edit distance with keyboard-neighbour, doubled-letter and swap costs, run-together splitting; `spelling.fix`; `utilities._heard` and `commands.read_typed` both call it) but its vocabulary is the asking words, so action and object words are only repaired when listed. Plan: build the speller's dictionary from the registries instead of by hand (every command and `/` command name, tool name and alias, utility trigger word, surface and category word, the notebook's own title, tag and category words), use one repair pass in front of every router (utility, command, search, `/`), run the topic of a search through fuzzy matching against the notebook's words and phrases (the composer already fits topic terms for scoring, `composer._fit_terms`; make it widen the search, not only the scoring), and always say what was assumed ("Read as: search the web for sandwiches") with the original one tap away. Add the owner's typos as fixtures (`fixtures/composer`) and a typo generator test: every registered command phrase with one keyboard-neighbour slip, one swap, one dropped and one doubled letter must route as the clean phrase does.
- Chat while the AI answers (owner, 2026-10-12, screenshots): (1) "the bottom of the chat area gets cut off a bit, and its completely cut off": the pending or streaming bubble sits under the composer dock with the "Still writing" pill showing, so the follow-to-bottom has stopped or the scroller reserves no room for the dock; measured with the stream stalled at 1440x900 the scroller ends 8px above the dock (bottom 663, dock top 671) and the pending bubble fits, so the cut-off needs a growing reply to reproduce (stall a stream with a script that sends deltas on a timer). (2) "scrolling on the chat area is slow and glitchy while the ai is responding": the live renderer re-renders the answer from raw Markdown every frame (`liveMarkdownRenderer`) and the `is-streaming` caret, the progress line and the timer repaint under a scrolling layer; profile scrolling during a stream at a 6x throttle, then cap the render to one per frame, render only the changed tail block, and give the scroller `contain: content` and the bubbles `content-visibility: auto` once finished.
- Composer ranks the tools the model is offered (owner, 2026-10-12): the composer reads a question's key words (after type repair) and scores every tool by how likely it is wanted, as a probability or percentage per tool, and that ranking decides the order and the cut: the top tools first, the least likely dropped first when the window is small. Why now: on 2026-10-12 `web_search` was appended last and so cut first on a small window, and the model, told about web search but not given the tool, thought for 150 seconds (fixed for a web ask with `tools.keep_first_for`; a general ranking removes the whole class). What exists: `toolwords.focus_detail` (keyword groups, `Focus.ranked` scores, `cues`), `tools.within_budget` (keeps `keep_first` or CORE_TOOLS first, then drops at the tail) and `composer_digest.asks_web`. Plan: one scorer, `rank_tools(question, history) -> [(tool, p)]`, built from the tool registry (names, aliases, descriptions, argument words, the `/` command registry) plus the repaired key words, entities (dates, notes, tags, places) and the previous turn's tools; `within_budget` consumes the order instead of a fixed list; the scores are logged in Settings, Logs ("offered: search_notes 0.92, web_search 0.81, create_note 0.12, held back ...") and shown in the "why" lines of a turn; a low top score offers a broader set and a clarifying question rather than a guess. Measure it: a fixture set of questions with their expected tools; report recall of the needed tool within the top 3, 5 and the budget cut, per model window size, against today's `focus_detail` ordering, before switching.
- A tool to list the tools, and the skills (owner, 2026-10-12): the model can ask what it can do. Checked first: `list_skills` and `run_skill` exist (tools/__init__.py, in a keyword group, so a small window may not offer them) but no tool lists the tools; `tool_catalog()` builds that list for Settings only. Add `list_tools(filter?)` returning every registered tool as name, one-line description, group, and a state (offered this turn, available but held back by the window, off in Settings, needs web search or another setting turned on, needs Agent mode), and `describe_tool(name)` returning the full schema and a worked example (`call_example`), so a model that reaches for something it was not shown, or is asked "what can you do", looks it up instead of guessing or saying it cannot. Same for skills: `list_skills` always reachable (core, one line of schema) with each skill's name, purpose, inputs and whether it needs a tool that is off. Both are read-only, cost one short schema each, answer in words and a panel in the bubble (the readable-results rule), and the held-back state feeds the tool-ranking entry above so a held-back tool can be pulled in on request, which also covers the 2026-10-12 web case.
- Activity panel, Agent runs tab: per-run actions and per-run detail (owner, 2026-10-12, screenshot with two finished runs, "Warming up the filing model" and "Describing sketch-...": "no way to delete or clear individual agent runs and also no way to see the logs or background process or status of each process"). Today: the panel's kebab has "Clear finished runs" (all at once) and "Show the log" (one shared log), and a run is an in-memory object (`agentRuns` in agent-activity.js, `addAgentRun`/`endAgentRun`) with a fold that is disabled when it has no steps, so a background job such as filing-model warm-up or a picture description has nothing to open. Build: (1) a kebab on every finished run (the `kebabMenu` recipe, DESIGN.md recipe 11): "Remove this run", "Copy its details", "Open its log", "Stop" while it runs; (2) every run opens to a facts block even with no steps: what it is, who started it (a chat turn, a skill, the night pass, an import, the app), state with the exact reason when it failed, started, finished and how long, the model used, tokens, the notes or files it touched (clickable), its own log lines filtered from the shared log (`/logs` by job id), and the next retry or schedule for a background job; (3) persist the last runs server side (a small `activity_runs` table, pruned to the last 100 and 30 days, Alembic revision) so a reload keeps them and Settings, Background tasks shows the same rows; (4) a filter (running, finished, failed) and "Clear failed" beside "Clear finished"; (5) the status bar's "2 runs" chip opens this tab. Help moves with it (standing order 13: the Activity panel's `data-help-for`, the Guide's topic and `tests/test_manual_parity.py`).
- Composer probe, 2026-10-12 (19 everyday questions through the no-model route; 16 answered well: counts, date, percentages, conversions, lists, tags, categories, reminders, greetings, capability, how-to, navigation): found and fixed "which note mentions perth" (the word "mentions" was searched for as a subject; now an asking word). Found, not fixed: (1) "oldest note" answers "Nothing comes up for “oldest”": `list_notes` has no order argument (`tools/__init__.py` orders `created_at desc`); add `order: newest|oldest` to the schema, `tool_say` lead ("Your oldest note is ...") and the route's retrieval for the question; (2) "what did i write yesterday" with no note that day answers the generic "I couldn't find any saved notes matching that question": it should say "You didn't write any notes yesterday. Your last one was on <day>" (the cadence facts in `composer_digest` already hold the last-note date); (3) "when is my dentist appointment" answers with the booking note but adds "None of these notes mention “appointment”": treat appointment, booking, booked, check-up, visit as one meaning group in the synonyms (`composer._build_synonyms`) so the unmatched-word line stays quiet when a synonym is present.
- Facts change over time (owner, 2026-10-12): the notebook, the AI and the composer must treat what a note says as true as of when it was written, so a newer note about the same thing supersedes an older one instead of confusing the answer. Example: a note on which days are uni days and which classes are taken this semester, then a similar note next semester; "what are my uni days" must answer from the newest, and mention the older only when comparing, noting the change, or being asked for it ("last semester you had Tuesday and Thursday; now Monday and Wednesday"). What exists to build on: `as_of` and `as_of_revisions` in the stream meta (answer as of a past date), `composer._disagreements` (names two notes that may disagree), the cadence and date facts in `composer_digest`, note `created_at`/`updated_at` and revisions. Plan: (1) recognise a recurring subject, a "state note" (schedule, address, job, plan, price, goal, routine, a list of current items), by shared entities, title shape and category across notes (embedding similarity plus the shared nouns), and link the pair as "supersedes" with a confidence; (2) retrieval ranks the newest of a superseding set first and marks older ones as past ("from March, since replaced"), never silently dropping them; (3) the composer answers with the current one, adds one line when an older one conflicts ("An older note, from semester 1, says Tuesday and Thursday"), and compares on request ("what changed since last semester": a rule-built diff of the two notes' lines); (4) the model is handed the dates with every note and the instruction to prefer the newest and to say when it is using an older one; (5) validity words in a note ("this semester", "until June", "as of 3 Oct", "from next week") are parsed into a validity window the engine uses to mark a note current, upcoming or past, and the notebook surfaces a gentle "this looks out of date" prompt when a window has ended or a newer similar note exists, with Merge, Keep both and Archive as the choices; (6) a timeline view per subject ("your uni days over time"). Measure with fixtures: pairs of state notes a semester apart plus questions whose right answer is the new one, the old one, or the change; check that the stale answer never appears unmarked.
- Companion double-click leaves it floating (owner, 2026-10-12): double-clicking the companion to resize it leaves it stuck at that spot on the screen and floating, no longer perched on whatever it was perched on (a card, a bar, the dock). Reproduce with the double-click on a perched companion, then read the perch state (`companion-*.js`: where the anchor is kept, what the resize path writes: likely an absolute left/top that replaces the perch's anchor and is never handed back). Fix: resizing must keep the anchor and re-derive the position from it (perch offset in the anchor's frame), or re-perch on the nearest surface after the resize settles; add a sweep (perch, double-click, resize, scroll the anchor, check it follows).
- Mind map pan with a node selected (owner, 2026-10-12, "insanely laggy ... maybe even more so now"): measured and fixed. A 120-topic map, a wheel pan with a topic selected, 4x CPU throttle: 71.8 s for 80 steps, 65 s of it in `wbUpdateSelectionBar` (rects, the topic's rendered size, the strip refilled, one forced layout of the board per frame); my first fix (hold the bar's measures) made a slow pan worse because every wheel gesture end re-measured in full. Now: the bar's measures and the selection box are held for the whole pan and the exact placement runs once, 250 ms after the pan goes quiet: 3.8 s, the same as with nothing selected, bar cost 24 ms. Not verified: a real GPU window (blurred panels over the canvas are not costed in a headless run), a drag pan with the Pan tool, and a pinch zoom.


## Owner's list, 2026-10-13 (one batch, in one place)

- **Composer, the whole batch (owner, 2026-10-13, verbatim; screenshots in the session):** "The composer needs more understanding, it still has a lot of flaws." Sub-items, each also a row on its own below where it has detail.
- **Magic add-on wording through the composer (owner, 2026-10-13):** the composer refines the magic add-on's reminders (bad sentence grammar, spelling mistakes, intent) the same way it refines the Ask digest; the wording rule lives with the magic add-on, the wording engine is the composer's.
- **Harper / Autocorrect with a hover-confirm (owner, 2026-10-13, verbatim; the click-reverts screenshot):** "Autocorrect on reminders and other app surfaces with harper, maybe other libraries and the composer, but also subtly highlight or colour the change for the user to notice in case it is wrong, then the user can hover over it and confirm it, edit it, or rewind the change." The 2026-10-12 click-reverts report (the blue-underlined word reverting the instant it is clicked; the owner wants a small undo popup near the word for confirming or reverting instead) is recorded here as a proposal, not as a settled fix.
- **More variation in composed lines, not only the greeting (owner, 2026-10-13, verbatim; the "Ready for the day, Brayden" screenshot, the question-mark note):** "Should this have an '?'?? I want the composer to have more variation, could it be more dynamic and actually come up with responses like an ai and not just preprepared responses?? idk". One set of variation rules for every composed line that the same digest feeds, not one-off grammar for the greeting.
- **Unusual input (owner, 2026-10-13, verbatim; the single-word "test" screenshot answered with a note that does cover it):** "This is alright but I feel like it should have acknowledged that it could be a test note?? Don't just account for this exact example, the composer needs to respond well to anything like this or similar scenarios. Like what if the user just button mashes or does a random string of keyboard charracters?? The composer needs to be like apple's siri with the same utility and usefullness and decent responses but better". A family of "unusual input" lines: a single word, a button-mash, a nonsense string, each with its own expected line, in the same fixture set as the owner's typos (BACKLOG "Type tolerance everywhere").
- **The composer is "Atlas's Assistant", the models are Atlas (owner, 2026-10-13, verbatim):** "Also the composer is 'Atlas's Assistant' and the ai models are Atlas themselves, it shouldn stay composer. Also it should probably tell the user that it is the assistant and if they want to talk to atlas, they should connect a model. And it should also give a composed general rundown of capabilities. This should be composed and not a set response, with variations, longer or shorter based on response style and user request etc. if the user asks about specific features or more yk??". Two rows: the naming across every surface that names the composer (the help parity lint covers it), and a composed capability rundown with variation.
- **The note-type switch disagrees after a switch and back (owner, 2026-10-13, verbatim):** "I switched from a md document to a code document and then back to md but it still thought it was and treated it like a code document." The editor's mode and the note's type must not disagree; a sweep is a switch to code and back, then check the editor and the note.
- **The packaged app's own desktop window is uninstallable (owner, 2026-10-13, verbatim; the Packages list screenshot):** "I shouldn't be able to uninstall the desktop view in the packaged windows app". When the app runs from the frozen exe, hide the Desktop window (pywebview) row's Remove action; keep Reinstall.
- **"Recent notes" answers as raw notes (owner, 2026-10-13, verbatim; the "recent notes pls" screenshot):** "Composer still needs a lot of refining and fixing. It is still very buggy, lacks a lot of understanding, and just straight up gives me the note back to me without any actual composing in the ask tab." Also the "What have I saved recently?" screenshot answered "I found no mention of 'saved'" over notes that did match. Two rows in the same step: the recent-notes answer composes (a lead and a composed list), and the keyword-miss line stays quiet when notes did match on a synonym.
- **"Tessellate" as a taxonomy option (owner, 2026-10-13, verbatim; the Tidy modal screenshot):** "Add tessellate as a taxonomy option". One row in the same step as the "uni/studies" row below; the pack's gold notes re-run.
- **A "uni/studies" category, and notes about the app's own features must not match study notes (owner, 2026-10-13, verbatim; the "I need to lock in for work, I have two design final assignments due next Friday" note auto-filed under "About Tessellate" at 68%):** "It filed my newest note about uni assignments in the about tessellate category?? That's wrong and now I need to go and manually change it and probably make a uni or studies or smth category idk".
- **The composer does "Improve writing" and "Generate title" (owner asks, 2026-10-13, verbatim; the note's context-menu screenshot shown with no model running):** "Can the comoposer do these ai actions well and just as good?? And they arent ai actions If the comoser does them when the ai isnt available". The owner is asking whether the composer can reach the model's quality on each act; the model's own answers are the gold to measure against, not a settled commitment to match them. Two rows: the composer runs each act, and the menu's label names the composer when it is the composer that does them.

## Placed from INBOX 904 (the owner, 2026-10-17)

- **MCP over HTTP with a scoped token (B52):** today `mcp_server.py` is stdio only, with no network listener, OAuth or token (trust is the local process, like `tessellate.db`). The owner wants a link to hand to Claude or another AI, easy Docker setup, and a token that limits which notes and tools that client sees. Design first: an HTTP (streamable) transport on the app's port behind a per-client token the person creates in Settings, scopes (categories, tags, read-only or read-write, no private notes), a revoke button, a log of what each client did; OAuth only if a remote client such as claude.ai requires it. The destructive-tools exclusion stays.
- **Managed local server instead of localhost (B28):** research a stable local name and port (a hosts entry or mDNS name such as tessellate.local, a fixed port with a fallback, an optional service install) and what it costs in the packaged build; no code until the owner picks.
- **Composer rows from the same list** are in `archive/agent-remaining/composer-1017.md` (the Opus brief): Chat and the needle path on Ask's engine, Guide intent, type tolerance, wording and Harper, slash commands, the AI actions with no model, magic add, digest and patterns, tool naming and ranking, facts over time.
- **Placed in their plans, from the same list:** document templates, snippets with drag, manage mode and live-view tables (DOCUMENTS_PLAN); diagram elements and templates, draw.io-style pan, a document viewer object (WHITEBOARD_PLAN); the timeline as a calendar (TIMELINE_PLAN Phase 5); more workflows (AGENT_SKILLS_REFORM); profile avatar life and the hardware card for suggested models (BACKLOG, this section's heirs).

1401. **The owner, 2026-10-27, verbatim.** "Should needle come packaged or vendored by default with the repo?? Should we use any other vendored small models like system-one laya or CDMS? Idk just a thought". Recommendation, taken: needle stays out of the repository (decision of 699: a 36 MB native engine plus weights per platform; pinned SHA-256 download, network symbols refused at install). Open as a build row: the Windows installer may carry it as an optional "offline bundle" so a fresh install needs no download. Laya stays not adopted (391: below a plain baseline zero-shot, weak past 20 labels, 512-token context). "system-one" and "CDMS" are not identified in this repo: the owner to name the projects before they are assessed (licence, size, an eval set showing a gap).
