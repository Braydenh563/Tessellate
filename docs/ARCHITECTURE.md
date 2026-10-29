# Tessellate: Architecture & Project Guide

> What Tessellate is, how it is built, and where everything lives. Read this
> once and you can find your way around the codebase.
>
> To install and use the app, see [INSTALL.md](INSTALL.md) and the
> [README](../README.md).

---

## 1. What it is

Tessellate is a **100% offline, local-first personal notebook**. You type a
thought; a local AI files it into a category automatically. Later you ask a
question in plain English and get back **both** a conversational answer **and**
the raw notes that matched. Everything (your notes, the search index, the AI
models) runs on your own machine, and nothing is sent to the cloud.

Around that loop sit seven tabs (Dashboard, Notes, Chat, Graph, Library,
Timeline, Reminders), a long-form document editor reached through the Library,
boards and mind maps, an assistant called Atlas that can act on the notebook
through a registry of tools (§7), and Settings. A **space** is a separate
notebook inside the same app.

The core loop:

```
capture text → AI categorises it → store it → ask a question → chat answer + raw results
```

## 2. Design principles (the rules everything follows)

These are the constraints that shaped every decision. When in doubt, they win.

1. **Offline-first, always.** No feature may depend on a cloud service. Two
   opt-in features can reach the internet, web search and the update check:
   web search is off by default, the update check waits for the answer to a
   question the first start asks once, and both are clearly marked. The rest is a short list of
   one-off downloads that you start (a model, an optional package) or say yes to
   (the search model, asked once); [PRIVACY.md](PRIVACY.md) lists them all and
   Settings, Privacy records every connection the app makes. When web search
   *is* on it is built to reveal as little as possible: an ordinary
   browser User-Agent rather than one naming the app, no cookie jar, no
   Referer, DNT/Sec-GPC set, POST so queries stay out of request lines, and
   tracking parameters stripped from result URLs. It has its own settings
   screen (`settings-websearch`), not a corner of the Profile pane, because
   every message that has to explain it points there by name.
2. **Degrade gracefully.** If the AI (Ollama) is down, the app still works:
   new notes are filed as `Uncategorised`, search falls back to keywords, and a
   status bar at the foot of the window says what the AI is doing. **Saving a note must
   never fail because the AI is unavailable.**
3. **Your data is yours, in plain files.** SQLite + JSON on disk, in a folder
   you can back up, inspect, or delete. Full JSON/CSV/Markdown export built in.
4. **Additive schema migrations.** The database upgrades itself at startup by
   adding new columns in place. Users never delete their database to update.
   (Alembic sits behind that for a rename or drop; see the Migrations note in §8.)
5. **Single source of truth for shared state.** Exactly one `ConfigManager` and
   one `DatabaseManager` per process, created in `core/deps.py`. Nothing else
   constructs them.
6. **Destructive AI actions are always confirmed.** The chat agent can act on
   your notebook, but deletes (and similar) pause for a user confirmation
   instead of executing silently.
7. **Tests are fast and fully offline.** Every AI call is faked in `tests/`, so
   the suite needs no GPU, no models, and no network.

## 3. The big picture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (frontend/: vanilla HTML/CSS/JS, no framework)      │
│   capture · ask · graph · chat · settings · voice · PWA      │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (same origin, no CORS needed)
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI app (src/tessellate/api/)                            │
│   routes_* → everything behind a single-user unlock gate     │
└───────┬───────────────────┬───────────────────┬─────────────┘
        │                   │                   │
┌───────▼──────┐   ┌────────▼────────┐   ┌──────▼──────────────┐
│  entry/      │   │  ai/            │   │  search/            │
│  create/read │   │  janitor        │   │  keyword + semantic │
│  + audit log │   │  librarian      │   │  (falls back safely)│
│              │   │  agent + tools  │   │                     │
│              │   │  embeddings     │   └─────────────────────┘
│              │   │  voice          │
└───────┬──────┘   └────────┬────────┘
        │                   │
        │          ┌────────▼────────┐        ┌───────────────┐
        │          │ provider        │───────▶│  Ollama       │
        │          │  ├ ollama_client│        │  (localhost)  │
        │          │  └ openai_client│───────▶│  LM Studio /  │
        │          │ (local REST)    │        │  llama.cpp /  │
        │          └─────────────────┘        │  Jan / vLLM   │
        │                                     └───────────────┘
        │
┌───────▼──────────────────────────────────────────────────────┐
│  core/: config · database (SQLite) · deps (singletons) ·      │
│          backup · logbuffer                                   │
│  data/ (gitignored): memorymap.db · preferences.json ·        │
│                       uploads/ · backups/ · logs/             │
└───────────────────────────────────────────────────────────────┘
```

## 4. Request lifecycle (two examples)

**Capturing a note** (`POST /entries`):

1. The route hands the text to the **janitor** (`ai/janitor.py`).
2. The janitor tries the cheap path first: embed the note and compare it to each
   category's centroid. A clear match files it with no LLM call at all.
3. Borderline or unknown → **one** call to the chat model, which returns a JSON
   category decision.
4. No AI available → `Uncategorised`, confidence `0`. The note is always saved.
5. The entry is written to SQLite, its embedding is stored, and the action is
   recorded in the audit log.

**Asking a question** (`POST /chat/...`):

1. **Search** (`search/`) retrieves candidate notes, semantic when embeddings
   are available, keyword otherwise.
2. The **librarian** (`ai/librarian.py`, strictly read-only) feeds those notes
   to the chat model with a grounding instruction: *answer only from the notes.*
3. The user gets the conversational answer **and** the raw matched notes side by
   side. If the model is offline, they still get the raw notes plus a friendly
   note that the AI answer is unavailable.

**Agentic chat** (`ai/agent.py`) is a superset of the above: the chat model is
offered a tool registry (see §7) and can *act*: create, tag, pin, link notes,
set reminders, looping tool-call → result → repeat until it produces a final
answer. Destructive tools don't execute inline; they emit a `confirm` event to
the UI.

## 5. Directory map

Checked against the tree on 2026-10-05. One line per module; the first
line of each module's docstring says the same thing at greater length.

```
Tessellate/
├── src/tessellate/
│   ├── __main__.py          # entry point: `python -m tessellate [--desktop |
│   │                        #   --export | --reset-password | --capture |
│   │                        #   --reinstall]`
│   ├── __init__.py          # __version__
│   ├── mcp_server.py        # `python -m tessellate.mcp_server`: a stdio MCP
│   │                        #   server over the non-destructive tools
│   ├── core/                # the machine: config, database, jobs, security
│   │   ├── config.py        # paths + user preferences (ConfigManager)
│   │   ├── database.py      # SQLAlchemy models + additive auto-migrator
│   │   ├── deps.py          # THE singletons (config, db, ollama, embeddings)
│   │   │                    #   + store_quietly(): best-effort embed
│   │   ├── events.py        # the event log: every change is a fact, the
│   │   │                    #   tables are views (WORLD_CLASS_PLAN B1)
│   │   ├── jobs.py          # the one bounded worker pool: two lanes (cpu for
│   │   │                    #   Tesseract and extractors, one worker for the
│   │   │                    #   model), every *_in_background enqueues
│   │   ├── jobstore.py      # the durable half: a `jobs` row per queued
│   │   │                    #   reading or filing, leased and heartbeated
│   │   │                    #   while it runs, resumed at launch after a
│   │   │                    #   quit or a kill; GET /jobs, /jobs/stream
│   │   ├── jobruns.py       # when each kind of job last ran and how it went:
│   │   │                    #   one `job_runs` row per kind, written through
│   │   │                    #   `job_run(kind)`, read by GET /jobs/last-runs
│   │   ├── bgtasks.py       # quitting background work: one job, or all
│   │   ├── taskhistory.py   # "recently finished" (in memory) for Settings >
│   │   │                    #   Background tasks
│   │   ├── filejobs.py      # which files the models are reading right now
│   │   ├── media_process.py # where OCR, captioning and vision OCR are
│   │   │                    #   triggered for an upload
│   │   ├── ocr.py           # local Tesseract OCR; `engine_status` reports
│   │   │                    #   program, Python part, version and language
│   │   ├── pdfpages.py      # a PDF page -> a PNG (optional `pdfpages` extra)
│   │   ├── docview.py       # any file -> its text (the viewer + import path)
│   │   ├── docmeta.py       # a document's frontmatter, read for the list
│   │   ├── docexport.py     # a document's markdown -> a file to hand on
│   │   ├── filetypes.py     # the one table of document types
│   │   ├── syntaxcheck.py   # syntax diagnostics for code documents
│   │   ├── backup.py        # daily local snapshot + restore
│   │   ├── backup_bundle.py # the full backup: one zip, optionally sealed with
│   │   │                    #   a password (`.mmenc`), and its restore
│   │   ├── diskspace.py     # what the app does when the disk fills
│   │   ├── extras.py        # the ALLOWLIST of pip-installable extras
│   │   ├── extra_downloads.py # the pinned-download kind of extra (needle, Pyodide)
│   │   ├── embedmodels.py   # the same shape for embedding models
│   │   ├── hardware.py      # this computer's memory, for the Models fit badges
│   │   ├── readings.py      # every reading of a file, in one shape
│   │   ├── imagesize.py     # an image's width and height from its header
│   │   ├── model_gate.py    # interactive model calls go before background ones
│   │   ├── usage.py         # the local usage ledger: which features you use
│   │   ├── security.py      # OriginCheckMiddleware, backend-URL local lock
│   │   ├── egress.py · privacy_http.py # every outbound connection recorded;
│   │   │                    #   the HTTP that keeps the privacy promises
│   │   ├── webclip.py       # the web clipper: one page, fetched once, kept
│   │   ├── netbind.py       # which address the server listens on
│   │   ├── lancert.py       # the self-signed certificate LAN mode serves
│   │   ├── instance_lock.py # one running server per data directory
│   │   ├── vault.py         # the private-note key, derived + held in memory
│   │   ├── crypto.py        # scrypt key derivation, encrypt/decrypt
│   │   ├── atomic_io.py     # temp-file + fsync + rename for preferences.json
│   │   ├── logbuffer.py     # in-memory log capture + safe_value()
│   │   ├── subproc.py       # spawn a child process without a console
│   │   ├── quit_hook.py · window_hook.py # how the launcher quits the app and
│   │   │                    #   toggles full screen for the desktop window
│   │   ├── launch_status.py # the launcher's status file, parsed
│   │   ├── startup_status.py# the current boot phase, for the lock screen
│   │   └── media_gc.py      # sweeps orphaned /media uploads
│   ├── entry/               # notes
│   │   ├── manager.py       # create/read/update/soft-delete, links, audit
│   │   ├── tagnames.py      # the one rule for what a list of tags may hold
│   │   ├── app_import.py    # Notion, Obsidian, Evernote, Apple Notes and a Tessellate folder in
│   │   ├── export_folder.py # the whole notebook as a markdown folder, and back
│   │   ├── import_report.py # what an import read, wrote and left out, kept as a page
│   │   ├── properties.py    # a note's `---` properties block (KG4)
│   │   ├── timewords.py     # what "tomorrow" meant, resolved at capture
│   │   ├── duplicates.py    # near-duplicate finder + AI merge
│   │   ├── highlights.py    # `==words==` highlights: text in a note, not rows
│   │   ├── opens.py         # how often each note is opened, a row per day
│   │   ├── bin.py           # the recycle bin for documents and reminders
│   │   ├── query.py         # live queries over the notebook's structure (KG7)
│   │   ├── importer.py      # uploaded document -> markdown (markitdown)
│   │   ├── mentions.py      # backlinks with their sentence, unlinked mentions (KG1)
│   │   ├── paths.py         # the shortest chain between two notes
│   │   ├── topics.py        # named subjects inside each cluster (KG6)
│   │   └── staleness.py     # notes nobody has touched, nothing points at
│   ├── ai/                  # everything that talks to a model
│   │   ├── provider.py      # what every backend must answer (§6)
│   │   ├── ollama_client.py # Ollama's native /api dialect
│   │   ├── openai_client.py # /v1/chat/completions: LM Studio, llama.cpp,
│   │   │                    #   Jan, vLLM
│   │   ├── model_manager.py # list/pull models, pick chat/embedding backend
│   │   ├── model_cards.py   # what a Settings model card says: size, memory
│   │   │                    #   needed, good for, whether it fits (`decorate`)
│   │   ├── sampling.py      # sampling parameters: model default, task, yours
│   │   ├── presets.py       # quick/normal/detailed (§11)
│   │   ├── context.py       # sizes one turn against the model's window
│   │   ├── budget.py        # the per-run budget: tokens and seconds
│   │   ├── embeddings.py    # embedding service + background warm-up
│   │   ├── provider_http.py # `requests` for the backends, redirects held
│   │   ├── janitor.py       # prompt: file a note into a category
│   │   ├── lexical_filing.py# filing with no model: the notebook's own words
│   │   │                    #   pick the category (`suggest_categories`) and
│   │   │                    #   the tags (`suggest_tags`)
│   │   ├── librarian.py     # prompt: answer from retrieved notes
│   │   ├── grounding.py · intent.py · drafter.py · followups.py
│   │   │                    #   what is being asked, grounding the answer,
│   │   │                    #   drafting it, what to ask next
│   │   ├── agent.py         # the tool-calling loop (§7)
│   │   ├── answer_trim.py   # strips the padding a model puts round an answer
│   │   ├── fence.py         # text from outside, fenced as quoted data
│   │   ├── source_check.py  # verify an agent answer against its sources
│   │   ├── when.py          # a time in your words, resolved by the app
│   │   ├── timetravel.py    # time travel over meaning
│   │   ├── questions.py     # open questions: the list and its states
│   │   ├── margin.py        # the margin reader: a second reader in the editor
│   │   ├── inbox.py         # the suggestions inbox's recognisers (KG9)
│   │   ├── bench.py         # the model bench: which model is best here
│   │   ├── skill_folder.py  # a skill is a Markdown file in a folder
│   │   ├── tools/           # the agent's tool registry, one file per area
│   │   │                    #   (`contracts.py` checks each tool's before and
│   │   │                    #   after; `board_edit.py` edits a board)
│   │   ├── toolwords.py     # which tools a request plausibly needs
│   │   ├── cards.py         # tool results as typed cards, not prose
│   │   ├── skills.py · skill_runner.py # what a skill is; running one (§7b)
│   │   ├── autonomous.py    # the background librarian: a scheduled pass
│   │   ├── facts.py         # what the notebook worked out for itself (I1, I9)
│   │   ├── learning.py      # what it learned from being corrected (I7)
│   │   ├── resurface.py     # three notes a day slipping out of reach (I4)
│   │   ├── tensions.py      # where the notebook disagrees with itself
│   │   ├── notebook_stats.py# questions about the notebook's shape, from SQL
│   │   ├── memory.py        # what you taught the AI to remember (persona)
│   │   ├── passive_capture.py # an offhand mention in chat -> a note to review
│   │   ├── extractor.py     # free text -> AI-drafted, linked notes
│   │   ├── links.py         # the reason two notes are linked
│   │   ├── relations.py     # pairs worth linking, every reason with its confidence (KG2)
│   │   ├── entities.py      # people, places, things (opt-in)
│   │   ├── reminder_parser.py # "call mum tomorrow evening" -> a due_at
│   │   ├── captioning.py · vision_ocr.py · docreader.py # an image read
│   │   │                    #   three ways; a document read as it lands
│   │   ├── help_chat.py     # the in-app guide: app knowledge only, no notes
│   │   │                    #   (`help_topics_more.py` holds part two)
│   │   ├── extractive.py    # an answer with no model: the notes' own words
│   │   ├── needle_provider.py · tool_fallback.py · offline.py # tool calling
│   │   │                    #   with no model server; who answers a tool turn
│   │   │                    #   when the chosen provider is down; what would
│   │   │                    #   make the AI work, said from what is true
│   │   └── voice.py         # optional local Whisper dictation
│   ├── search/
│   │   ├── engine.py        # one search, three signals, every hit explained
│   │   ├── index.py         # one index over every kind (B3)
│   │   ├── search_manager.py# the entry point the routes call
│   │   ├── query.py         # search-operator parsing (tag:, cat:, is:pinned)
│   │   ├── chunks.py        # paragraph vectors, held in memory
│   │   ├── websearch.py     # opt-in web search and the reader: every request
│   │   │                    #   made for a search
│   │   └── searxng_*.py     # a local SearXNG: manager, install (from source),
│   │                        #   docker, process, settings
│   └── api/
│       ├── app.py           # builds the FastAPI app, mounts the frontend
│       ├── schemas.py       # Pydantic request/response models
│       ├── paging.py        # cursor pagination, one contract for every list
│       ├── versioning.py    # `/api/v1`: the notebook as a versioned service
│       ├── edit_conflicts.py# two windows, one note: the optimistic save check
│       ├── asset_strip.py   # comments out of CSS and JS, at serve time only
│       ├── run_sandbox.py   # the sandbox a code document's Run button uses
│       └── routes_*.py      # one router per feature area (see §6)
├── frontend/                # vanilla HTML/CSS/JS, served as-is, no build
│   ├── index.html           # the whole shell; every id is load-bearing
│   ├── js/                  # every script named below, except sw.js (a service
│   │                        #   worker only controls pages under its own path,
│   │                        #   so it stays here at the root)
│   ├── capture.html · clip.html # two small pages: `--capture`'s one-line
│   │                        #   window and the web clipper's window (their
│   │                        #   scripts are js/capture.js and js/clip.js)
│   ├── board-library/       # the whiteboard's built-in object library data
│   ├── theme-boot.js · boot-guard.js # before first paint: theme, perf mode,
│   │                        #   and the guard that reports a boot failure
│   ├── app.js … agent-activity.js # the shell, notes, chat and settings
│   │                        #   glue: 27 classic scripts, one file until
│   │                        #   2026-09-26, in index.html's order (app.js
│   │                        #   first: api, auth, the lazy loader;
│   │                        #   agent-activity.js, Agent Activity's list of
│   │                        #   runs, last); each file's header says what it
│   │                        #   holds
│   ├── icon-picker.js       # the one emoji and icon picker (with
│   │                        #   css/icon-picker.css); lazy, on first use
│   ├── nav-history.js       # the rows of the status bar's Back and Forward
│   │                        #   list (with css/nav-history-lazy.css); lazy
│   ├── chord-guide.js · batch-space.js · note-templates.js · companion-menu.js
│   │   · vault-unlock.js · help-chat.js · pick-row.js · drag-edge.js
│   │                        #   lazy, each out of a boot script: the key
│   │                        #   chord's panel, a selection's Move to space, the
│   │                        #   Capture box's template picker, the companion's
│   │                        #   menu, Unlock private notes, the Guide's chat,
│   │                        #   an Attach picker row, a drag-selection's edge
│   │                        #   scroll
│   ├── atlas-life.js · atlas-motion.js # Atlas's tail, ring loops and blink;
│   │                        #   lazy, the figure draws whole without them
│   ├── ask-chart.js · whiteboard-history.js # a chart from a counting
│   │                        #   question; a board's time machine; lazy
│   ├── settings-packages.js # Settings, Packages: the extras and their bundles;
│   │                        #   loaded when the section opens
│   ├── quick-note.js        # Quick note (Alt+N) and the offline note
│   │                        #   outbox; lazy, fetched a few seconds after boot
│   ├── tag-manager.js · chip-menus.js · tag-suggest.js # the tag manager and
│   │                        #   bulk tag dialog, the menus a category or tag
│   │                        #   chip opens, the tags field's own list; lazy
│   ├── categories-panel.js · note-history.js · ask-history.js # lazy panels
│   ├── lightbox-view.js · edit-conflict.js · attachment-actions.js
│   │                        #   lazy: the image viewer, the two-windows edit
│   │                        #   check, an attachment card's click
│   ├── ocr-engine.js        # the OCR workspace's Tesseract status line; lazy
│   ├── settings-data.js · settings-find.js · settings-models.js # lazy parts
│   │                        #   of Settings (data, search, model cards)
│   ├── settings-controls.js # every listener inside the Settings window; the first
│   │                        #   openSettingsModal awaits it
│   ├── reveal-targets.js · onboarding.js · update-dialogs.js · app-palette.js
│   │                        # lazy: catalogue deep links, welcome card, update check
│   │                        #   and dialogs, the Ctrl/Cmd-K palette's window
│   ├── note-panels.js · note-edit-panels.js · attach-to.js # lazy: a note card's
│   │                        #   menu panels and the edit form's two panels (one
│   │                        #   bundle), the put-on-a-board and add-to-document pickers
│   ├── settings.js          # Settings, appearance, whether the background art runs
│   ├── bg-art.js            # the background art: its styles and its runtime
│   ├── dashboard.js         # the dashboard's widgets
│   ├── timeline.js          # the Timeline tab: feed, table, scrubber
│   ├── library.js           # Library: files, images, the OCR workspace
│   ├── undo-store.js · margin-reader.js # lazy with the Library: the stored undo
│   │                        #   histories both editors read; the margin reader
│   ├── suggestions-inbox.js · entity-page.js · link-types.js · note-properties.js
│   │                        #   lazy: the suggestions inbox, an entity's page,
│   │                        #   kinds of link, a note's properties
│   ├── model-bench.js · web-clip.js · app-import.js · usage-ledger.js
│   │                        #   lazy Settings groups: the model bench, the web
│   │                        #   clipper, import from another app, the usage
│   │                        #   ledger
│   ├── field-clear.js · assistant-avatar.js · quick-access.js · notes-rail-spy.js
│   │                        #   · dash-boards.js · tag-suggest.js: small lazy pieces
│   ├── documents.js · editor.js # the long-form editor and its CodeMirror
│   ├── documents-code.js · documents-prose.js # its code tools and
│   │                        #   prose tools, loaded before documents.js
│   ├── graph.js · graph-canvas.js · graph-worker.js # the graph, its
│   │                        #   canvas renderer and its layout worker
│   ├── whiteboard.js        # boards, and the concept map of cards
│   ├── whiteboard-map.js    # mind maps: nodes, edges, tidy, themes,
│   │                        #   loaded before whiteboard.js
│   ├── whiteboard-commands.js · whiteboard-format.js · whiteboard-library.js ·
│   │   whiteboard-interchange.js # the board's command table, Format panel,
│   │                        #   object library, and Mermaid/SVG/outline in and out
│   ├── mermaid-frame.js · mermaid-draw.js # every ```mermaid fence: a hidden same-origin
│   │                        #   frame (own policy) runs vendor/mermaid, loaded on first use
│   ├── task-steps.js · gesture-kit.js · lag-watch.js · screen-context.js # task steps,
│   │                        #   shared pointer gestures, the slow-frame log, what the Guide sees
│   ├── sw.js · manifest.webmanifest # PWA
│   ├── css/                 # eleven files, 00-tokens-shell to 10-responsive;
│   │                        #   index.html's <link> order is load-bearing; and
│   │                        #   lazy sheets (icon-picker, library-lazy,
│   │                        #   nav-history-lazy, mermaid-lazy, glass-controls-lazy, math-editor-lazy, web-lazy) fetched with their scripts
│   └── vendor/              # d3 v7, p5, CodeMirror, Mermaid 12.2.0, Phosphor icons, the
│                            #   spelling wordlist: local, never a CDN
├── tests/                   # pytest; every AI call faked (tests/fakes.py)
├── tests-e2e/               # the Playwright smoke suite CI runs
├── migrations/              # Alembic's chain, behind the additive migrator
├── scratchpad/              # measurement scripts: ui-sweeps/, the fake
│                            #   OpenAI server, the INBOX tools, llama-dev.sh
├── scripts/                 # gate.sh, the merge gate in one command; the board
│                            #   library builder and the eval and scale scripts
├── docs/                    # you are here; roadmap/ holds the plans, screenshots/
│                            #   the README's pictures, index.html the docs site
├── packaging/               # the Windows installer and the Linux package
├── .github/                 # CI, CodeQL, Dependabot, issue/PR templates
├── start.sh · start.bat · start-desktop.sh · start-desktop.bat · uninstall.sh · uninstall.bat
├── requirements.txt · pyproject.toml · pytest.ini · alembic.ini
├── .env.example             # copy to .env to relocate data / set OLLAMA_URL
└── README.md · LICENSE · CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · IDEAS.md
    CLAUDE.md (the operating manual for any session, human or model)
```

## 6. The API surface

The app is a FastAPI server. Every router except `/auth`, `/health` and the
few open routes the sign-in page needs sits behind the single-user **unlock
gate** (`routes_auth.require_unlock`). Routers are grouped by feature area:

| Router | Prefix | Responsibility |
| --- | --- | --- |
| `routes_auth` | `/auth` | first-run password setup, unlock, lock, change password, account state |
| `routes_entries` | `/entries` | create/read/edit/soft-delete notes, links, related, restore. `POST /entries` takes an optional `client_key`: the offline outbox's resend of a save whose answer was lost returns the first note instead of making a second (`_already_delivered`, in memory, 512 keys). `POST /entries/{id}/suggested-tags` takes or discards the tags filing suggested |
| `routes_chat` | `/chat` | ask questions, streaming answers, agentic tools, suggestions |
| `routes_conversations` | `/conversations` | saved chat threads |
| `routes_ask_history` | `/ask-history` | the Ask tab's past question/answer turns, independent of saved chats |
| `routes_models` | `/models` | Ollama status, pull models, switch chat/embedding/utility model; `GET /models/suggested` (cards decorated by `ai/model_cards.py` with size, memory and fit), `GET /models/hardware` (`core/hardware.py`), `POST /models/inspect` |
| `routes_settings` | `/` | preferences, skills (`GET /skills`), audit log, JSON/CSV/Markdown export & import, logs, optional extras (`/extras`), embedding models (`/embedding-models`) |
| `routes_update` | `/update` | check GitHub for a newer release and apply it in place, instead of sending the user back through a browser to redownload the installer |
| `routes_websearch` | `/websearch` | web search provider selection + SearXNG install/start/status lifecycle, split out of `routes_settings` |
| `routes_backups` | `/`, `/backups` | `GET /storage` (where the data lives, how big it is) + daily local backup list/create/restore/delete |
| `routes_spaces` | `/spaces` | separate note "spaces" (workspaces) within the one notebook |
| `routes_documents` | `/documents` | long-form markdown documents, export, AI edit; `GET /documents/outline` is every live document with its headings and `created_at`, one request, for the Library's Contents tree |
| `routes_duplicates` | `/duplicates` | near-duplicate finder + AI merge |
| `routes_drafts` | `/drafts` | the writing room's compose/rewrite calls |
| `routes_files` | `/`, `/media` | attachments upload/download/delete; `GET /ocr-readers` says what can read a page (vision model, OCR model, and the Tesseract `engine` status). `media_router` (`/media`, pasted/dropped inline images) is a second router from the same file, gated by `require_unlock_media` rather than the ordinary unlock dependency: it accepts a query-param token, since an `<img src>` cannot carry a header |
| `routes_tags` | `/tags` | list, rename, merge, delete (several names at once), `POST /tags/bulk` (add or remove tags on many notes) and `POST /tags/restore` (the one Undo); each is one transaction with a revision and an event per note |
| `routes_categories` | `/categories` | list/rename/merge/delete categories, and a category's chosen colour |
| `routes_graph` | `/` | force-directed graph data + link suggestions |
| `routes_insights` | `/insights` | dashboard: stats, most-accessed, on-this-day, digest |
| `routes_reminders` | `/reminders` | create/list/complete reminders |
| `routes_bookmarks` | `/bookmarks` | saved links to somewhere outside the notebook, same shape as reminders, no AI involved; a link can be read, pinned and noted, and pages tile one order (pinned first) |
| `routes_voice` | `/voice` | local Whisper transcription |
| `routes_help` | `/help` | the Guide's chat (`POST /help/ask`), app guidance only, no persisted history |
| `routes_timeline` | `/timeline` | the notebook on a time axis, in bands |
| `routes_tasks` | `/tasks` | what is running in the background right now (`GET /tasks`), and `GET /jobs/last-runs`: when each kind of job last ran and how it went, one entry per kind in `jobruns.KINDS`, from the database so it survives a restart; `GET /jobs` and the server-sent `GET /jobs/stream`, the durable job rows (`core/jobstore.py`), and `POST /jobs/{id}/cancel` for a queued one |
| `routes_library` | `/library` | **everything you have made, in one list**: notes, documents, chats, files, tags, bin, activity, assembled server-side |
| `routes_whiteboard` | `/whiteboard` | note cards and freehand sketches on a pannable canvas (§39C). A *board* is itself an entry, so it is searchable and filable like anything else; `board_id IS NULL` is the unnamed scratch board |
| `routes_debug` | `/debug` | `GET /debug/health`: one cheap, under-20ms read across data that already exists elsewhere (running jobs, task history, the log), for "is this notebook okay" in one glance |
| `routes_search` | `/search` | one search over every kind of thing (WORLD_CLASS_PLAN B3) |
| `routes_learned` · `routes_night` · `routes_resurface` | `/learned`, `/night`, `/resurface` | what the notebook worked out for itself (facts you can correct), the night pass on demand, three notes a day slipping out of reach |
| `routes_mentions` | `/entries/{id}/backlinks`, `/entries/{id}/mentions/link` | a note's backlinks with their sentence and its unlinked mentions, one click to a [[link]] (GRAPH_PLAN KG1; the scanner is `entry/mentions.py`, shared with documents) |
| `routes_inbox` | `/suggestions`, `/suggestions/merges/*`, `/suggestions/types/*` | the suggestions inbox's entity merges and link types (`ai/inbox.py`), and every decision on them as a correction (GRAPH_PLAN KG9) |
| `routes_entities` | `/entities`, `/entities/{id}`, `/entities/{id}/merge` | the entity layer: the list, an entity's page (mentions in context, co-mentions, dates), kind, rename, other names and a merge by hand (GRAPH_PLAN KG5) |
| `routes_relations` | `/relation-types`, `/relation-types/{key}` | kinds of link: the six built-ins (code) and a person's own (`RelationType`), each with its name from the other end; a deleted kind leaves its links untyped (GRAPH_PLAN KG3) |
| `routes_properties` | `/entries/{id}/properties`, `/note-types` | a note's properties (the `---` block in its text, `entry/properties.py`; `EntryProperty` is the index) and note types with fields (GRAPH_PLAN KG4) |
| `routes_import` | `/import/app`, `/import/reports/{id}`, `/export/folder` | notes from Notion, Obsidian, Evernote, Apple Notes or a Tessellate folder (a job with Stop and a kept report); the readers and the writer are `entry/app_import.py` and `entry/export_folder.py` |
| `routes_questions` | `/questions` | open questions: the list and its states |
| `routes_editor` | `/editor` | `POST /editor/read`: the margin reader's one route |
| `routes_vision` | `/review-queue`, `/most-opened`, `/tidy-proposals`, `/charts/question` | the original vision's open rows: the review queue, most opened notes, tidy proposals and a chart from a counting question |
| `routes_board_history` | `/whiteboard/history` | a board's time machine: its event log, one event, and restoring the board or the selection to a moment |
| `routes_map_suggest` · `routes_map_from_notes` | `/whiteboard/boards/{id}/nodes/{id}/suggest` and `/branches` and `/summary`, `/whiteboard/maps/from-notes` | grow a map topic from the notebook, and make a mind map from the graph's own structure |
| `routes_bench` | `/models/bench` | run the model bench and read its report |
| `routes_usage` | `/usage`, `/capture` | the local usage ledger's door, and `GET /capture/command`, the exact `--capture` command line for this install |
| `routes_capabilities` | `/capabilities` | what this install can do, asked once |
| `routes_board_library` | `/board-library` | the whiteboard's object library: built-in sets, favourites, your own saved pieces |
| `routes_privacy` | `/privacy` | the privacy receipt: what left this machine, from the app's own egress record |
| `routes_webclip` | `/links` | `POST /links/clip`: keep a web page as a note, only while the web is allowed |
| system | `/health` | liveness + version (open, no unlock) |

There is no interactive API explorer: FastAPI's `/docs` and `/redoc` load their
scripts from a CDN, which the app's own Content-Security-Policy refuses, and the
schema would list every route to anyone who could reach the port. The schema is
served at `/openapi.json` behind the unlock, for tooling that sends the
`X-Auth-Token` header.

**`POST /chat/stream` is NDJSON over a plain POST, and that is a decision, not
an oversight.** It was rewritten as a WebSocket once and reverted, for four
reasons worth keeping written down because the rewrite looked like an upgrade:

- The agent loop is blocking, so a WebSocket handler has to run it on another
  thread, and the request's SQLAlchemy `Session` is not thread-safe.
- Nothing cancels that thread when the client disappears, so a closed tab
  leaves a model generating against a Session that is being torn down.
- A WebSocket route cannot carry `dependencies=locked`; auth has to be
  re-implemented by hand inside the handler, after `accept()`.
- **A WebSocket handshake is not subject to the same-origin policy.** A
  `fetch` from another origin is stopped by the browser; a `new WebSocket(…)`
  to `127.0.0.1` is not. For a local server holding someone's notebook, that
  is the whole argument on its own.

NDJSON over `fetch` delivers tokens exactly as promptly and has none of that.
The header `X-Accel-Buffering: no` is what keeps a reverse proxy from
defeating it.

**Anything that runs on a worker thread belongs in `routes_tasks.collect()`.**
Each job reports a label, a detail line, a `progress` fraction *only where one
is genuinely knowable*, whether it can be stopped, and the lines it has
printed. The log matters as much as the bar: pip building lxml sits on one
number for minutes, and its output is the only thing that distinguishes slow
from stuck.
Settings → Background tasks renders whatever that returns, so a new job shows
up there without the frontend being taught about it. It used to build the list
in `app.js` from the two jobs that happened to be in `/models/status`, which
is why the embedding warm-up and the multi-minute SearXNG install ran with
nothing on that screen to say so. Only *running* work is listed: a finished
job is not a task, and a screen that accumulates them is the Logs screen.

## 7. The agent's tools (Wave G)

`ai/tools/` (a package now: `__init__.py` plus `categories.py`,
`documents.py`, `files.py`, `whiteboard.py`, `_common.py`, split out once the
registry outgrew one file) defines a registry the chat model can call:
**72 tools**. Read-only tools run inline; the **destructive** ones (marked
⚠️ below) emit a confirmation event to the UI instead of executing. The
registry's `destructive` flag is the one list: a change after a turn has read
text from outside (a web page, a clipped or imported note) waits for the same
confirmation (SEC-02).

*Reading the notebook:* `search_notes` · `get_note` · `list_notes` ·
`count_notes` · `list_tags` · `list_categories` · `summarize_notes` ·
`find_similar_notes` · `related_notes` · `notebook_overview` ·
`find_contradictions`: notes that disagree with each other: a reversed
decision, a date that moved

*Reading everything else:* `list_documents` · `get_document` ·
`search_chat_history` · `get_current_time` · `search_files` · `read_file`:
uploads, photos, scans and attachments, by name, caption or the text read
out of them, which notes never contain

*Writing:* `create_note` · `edit_note` · `tag_note` · `pin_note` · `link_notes` ·
`unlink_notes` · `restore_note` · `rename_tag` · `delete_note` ⚠️ ·
`delete_tag` ⚠️ · `audit_link_reasons`

*Categories:* `create_category` · `rename_category` · `merge_categories` ⚠️ ·
`delete_category` ⚠️, by name, never by id, since the model has never seen
one. Deleting a category keeps its notes (they become Uncategorised); the
destructive ones are so because none is reversible afterwards: nothing
records which notes came from where, or which two notes an unlinked pair was.

*Documents:* `create_document` · `get_document` · `list_documents` ·
`delete_document` ⚠️

*Whiteboard (§37G):* `add_whiteboard_card` · `add_whiteboard_link` ·
`read_whiteboard` · `search_whiteboard` · `generate_diagram`: lay out a
whole diagram from a set of notes in one call

*Editing a board (FEAT-12):* `add_board_shape`: a rectangle, ellipse, diamond or
frame; `list_library` and `place_library_item`: search the board's object
library and place from it; `edit_board_item` ⚠️ (words, line colour, fill) ·
`move_board_item` ⚠️ · `delete_board_item` ⚠️, each returning an Undo, and
`restore_board_item`, the call that Undo makes

*Mind maps* (a board that is a tree, `ai/tools/whiteboard.py` alongside the
whiteboard tools above): `create_mindmap` · `read_mindmap` ·
`add_map_node` · `link_map_nodes` · `map_from_note` (a whole map from one
note's headings and lists, in one call)

*Planning and structure:* `make_plan`: a ticked-step plan shown in the chat
timeline; `notebook_structure` and `path_between`: the same graph traversal
the Graph tab's own "Trace" feature uses, so the agent can read the
notebook's structure rather than only search it

*Reminders:* `set_reminder` · `list_reminders` · `complete_reminder`

*Skills:* `list_skills` · `run_skill` · `save_skill` · `delete_skill` ⚠️

*Conversation flow:* `ask_user`: the model asks a clarifying question
instead of guessing which note you meant; `compress_chat` ·
`save_user_preference`: a standing instruction ("always answer in British
English") remembered across conversations

*Help, sums and checks:* `search_help`: how a feature or setting works, from the Guide;
`calculate`: a sum, percentage, unit or currency conversion, or count of days, worked out the
way the app does; `check_answer`: a draft answer against its sources, naming any number or
name they do not contain

*Proposing a change:* `propose_act` (one change in the person's words, shown as a card they
confirm) and `move_notes` (into a category or a space; the app asks first)

*Online (opt-in, off by default):* `web_search` · `read_url`

### The context budget

`ai/context.py` sizes **one whole turn** against the model's window before any
of it is assembled. Nothing else in the AI path holds a fixed character limit,
because the bug it replaced was that each part had one and nothing added them
up: the worst case came to ~11,328 tokens against a window that is commonly
4,096, and overflow is dropped from the *front* (the system prompt), so a
model that overflowed simply stopped knowing it had tools.

```
window  ──┬── reply reserve (15%)      kept back; num_ctx covers both
          ├── system prompt            measured, not assumed (persona is editable)
          └── the rest, split:
                tool schemas  30%      what the agent needs to act at all
                tool results  30%      capped by TOOL_RESULT_BUDGET_CHARS
                notes         25%   ┐  recoverable: the model can ask for
                history       15%   ┘  more (get_note, the visible thread)
```

**Two things then shrink the fixed half, and only on a small window** (§94).
Measured on 8k with eight notes and no history, the prompt was 32% of the
context before the conversation started, with tool schemas costing nearly
twice the user's own notes:

- `tools.compact_schemas` trims each tool's description to one sentence,
  touching no name, type or required-ness. `within_budget` tries this
  **before dropping any tool**, because dropping one changes what the app can
  *do* while trimming prose only changes how verbosely it is explained.
- `agent.tools_guide(window)` swaps the 2,807-char guide for a 1,034-char
  rewrite at or below 8k. That guide is re-sent every round, so on a 4k model
  it was 17% of the whole context per round.

Result: 23%. `tests/test_prompt_budget.py` pins the fixed half under 20% and
asserts at least eight tools survive, so the saving cannot come from quietly
handing the model an empty toolbox.

### Which tools are offered

`ai/toolwords.py` reads the request for the tools it plausibly needs:
deterministic, word-boundary matching, no model call, in the same shape as
`entry/timewords.py`. Substring matching offered the tag tools for "my vintage
camera" and the link tools for "blinking lights".

**It advises; it never decides.** `CORE_TOOLS` is always offered, a broad or
unreadable request gets everything, `agent.FOCUS_NOTE` tells the model the list
is a suggestion it may reach past, and a call for an unoffered tool widens the
set to everything for the rest of the turn. A misread costs one round, not the
request.

Notes and history yield first when space is short *because they are
recoverable*: `get_note` reads one in full, and the conversation is still on
screen. Notes are dropped whole rather than all clipped shorter (ten notes cut
to a sentence each are ten things the model cannot quote, four whole ones are
four it can), and the model is told how many did not fit. History is kept in
whole user/assistant pairs, since half an exchange invites the model to invent
the missing side.

`OllamaClient.runtime_options` then sends `num_ctx` **and** `num_predict` with
every generation. Both matter, and the first is easy to miss: Ollama runs a
model at its own `num_ctx` default regardless of what the model was trained
for, so budgeting against a declared 32k without also *asking* for it
reproduces the exact overflow the budget prevents. The number budgeted against
and the number requested are the same one.

**How many tools a turn actually sends** is decided in two steps, and neither
is a fixed number:

1. **Relevance**: `tools.focus_for(question)` reads the question for what it
   plausibly needs and returns ~8–12 tools. Keyword-driven rather than another
   model call: a round-trip to decide what to send would cost more than it
   saves, and a deterministic rule can be read, tested and argued with.
   Settings → Tools it can use can switch this off (`tool_focus: "all"`).
2. **Room**: `tools.within_budget` then fits whatever survives to the window
   the model *reports* (`ollama_client.usable_context`, from `/api/show`),
   spending at most `TOOL_SCHEMA_WINDOW_SHARE` of it on schemas. Anything that
   does not fit is dropped from the tail, and what was held back is logged.

This replaced a fixed character budget, which was the wrong shape: 4096 is
Ollama's *fallback* when a model declares nothing, not a fact about any
particular model. Rationing a 32k model against it withheld tools for no
reason; assuming otherwise on a real 3B dropped the system prompt off the
front, and a model that overflows stops knowing it has tools at all.

| Model window | Tools sent (whole registry offered) |
| --- | --- |
| 2,048 | 4 (core only) |
| 4,096 | 9 |
| 8,192 | 19 |
| 16,384 and up | all of them |

A skill's declared tool list is exempt from step 2: it asked for exactly those,
and silently dropping one would break the run rather than trim it.

> `agent.PROSE_BUDGET_CHARS` and `tests/test_prompt_budget.py` are the backstop
> on the **prose**: the system prompt and `TOOLS_GUIDE` are sent whatever the
> window and no per-turn trimming applies to them. There is deliberately no
> constant capping the tool *registry* any more: `within_budget` caps it
> against the model's real window instead, which is the only number that was
> ever a fact about anything.

`search_notes` and `list_notes` return **previews**, which is why `get_note`
exists and its description says so: a model that quoted a note from a preview
was quoting a truncation.

### Errors a tool is allowed to explain

Handlers raise **`tools.ToolError`** for failures they mean to explain ("no
note with that id"). Only that text is passed back to the model and out of
`POST /chat/tools/execute` to the user. A bare `ValueError`, `KeyError` or
`TypeError` from inside a handler is something else (whatever `int("abc")`
happened to say), so it is logged here and reported by *shape* instead. A
single `except ValueError` could not tell those apart, and the difference is
the one CodeQL flagged as stack-trace exposure.

### The per-round budget

Everything in this registry is serialised into the `tools` field on **every
round of every turn**, alongside the system prompt. That fixed overhead is
~3,050 tokens, and **77% of it is these schemas, not the prose in
`TOOLS_GUIDE`**: so a verbose new tool description costs more than a verbose
new paragraph.

`tools.within_budget` caps it against the window the model reported, per turn,
and `tests/test_prompt_budget.py` asserts what reaches a 4,096-token model
after that trim. A constant used to cap the whole registry; it was retired
after being raised three times for legitimate growth, because it measured a
case no turn has sent since the per-turn trim existed.

Why any of this matters: Ollama defaults to a 4096-token window and drops
overflow from the *front*, so a 3B model that overflows loses the system prompt
and stops knowing it has tools, which presents as "the AI won't use tools"
rather than as anything to do with length. Settings → Tools it can use
(`disabled_tools`) is the user-facing escape hatch, and it filters at
`ollama_tools()`, the wire, not just at execution.

**Adding a tool is not free.** If the budget test fails, that is the design
working; either trim, or raise the constant deliberately and say why.

**Not every turn is offered every tool.** `tools.focus_for(question)` reads the
message and returns the reading core plus whatever the words ask for:
`set_reminder` for "remind me…", `tag_note` for "tag my…". An ordinary
question therefore carries ~3,340 characters of schema instead of 10,215,
which halves the fixed overhead a 3B model reads before it reaches the
question. Two rules keep it honest: a request that sounds like a job but does
not say which one ("tidy up my notes") gets **everything**, and the focus is
an *economy, not a policy*: unlike a skill's allowlist it never stops a tool
from running, so a cue that fails to fire costs tokens, not abilities.
Settings → Tools it can use has the switch (`tool_focus`), because the honest failure of
a keyword rule is a phrasing it does not know.

**Two more rules hold the budget, and both are easy to break by accident:**

- **A note goes in short, and the model can ask for the rest.**
  `librarian.note_for_prompt` caps a note at `MAX_NOTE_CHARS` (900) and cuts
  with a marker naming the call that reads it whole (matching the code's own
  string exactly): `… [cut, call get_note(7) to read it in full]`. Retrieving
  ten notes is pointless if one
  note of several pages fills the prompt on its own. This is only safe because
  the truncation is *reversible*: `get_note` exists and `TOOLS_GUIDE` already
  tells the model to use it before quoting. **A cut the model cannot undo is
  just a missing piece of the note**: so if the marker or the tool ever goes,
  the cap has to go with it.
- **The front of the prompt must not move between rounds.** Ollama caches a
  prompt only up to the first difference, so anything volatile near the top
  invalidates everything below it. The clock in the system prompt is written
  to the *minute* for exactly this reason: at microsecond precision it
  differed on every round of every turn, and each round of a tool loop (whose
  rounds are seconds apart) re-read the whole prompt from scratch. Anything
  added above the history or the notes has to be stable for at least the
  length of a tool loop, or it costs a full re-read per round.

## 7b. Skills

A skill (`ai/skills.py`) is a **named, repeatable job over the notebook**, not
a saved sentence. It has a `prompt`, and optionally `steps` (ordered
instructions), `tools` (an allowlist), `inputs` (declared `{{placeholders}}`)
and a `description`. A skill with only a prompt is exactly what skills used to
be, so nothing was lost in the rebuild.

Three things are worth knowing before changing anything here:

1. **The declared tools are the only ones offered for the run.**
   `ollama_tools(allowed)` narrows the wire and `run_agent(allowed_tools=…)`
   refuses execution of anything outside the list, a safety property,
   not only a prompt. It is also §11a's win: the full registry is ~10,200
   characters of schema on *every round*; "Auto-tag my notes" ships 1,963.
   The user's own switches still win, so a skill can't re-enable a tool turned
   off in Settings → Tools it can use.
2. **Naming the tools in the instruction text is deliberate**, on top of
   narrowing the wire. The reported failure was a model that had tools and
   didn't know it was meant to act; telling a 3B model "use `tag_note`" is
   what makes it reach for one.
3. **The built-ins live in Python, not `app.js`.** They are served from
   `GET /skills` with the user's own, for the same reason the web-search
   providers are: the server has to be able to resolve a skill the user just
   clicked, and a field added to a skill should not need adding twice.

Running one is `POST /chat/stream` with `skill` and `skill_inputs`: the
server builds the instruction, so what a skill *is* lives in one place.
`skills.normalise` validates both ways in, the editor and `save_skill`, so a
skill the AI can write is one the UI can write, and neither can store one that
won't run.

**A skill with steps runs one step per turn** (`ai/skill_runner.py`), not one
request carrying a numbered list. A list inside one request is a plan the
model may ignore, and a 3B model given four instructions at once does the
first and narrates the rest. One turn per step means the app *knows* where it
got to, so it can tick each step off, name the step that failed, and keep each
turn small. Each step gets the previous steps as history. A skill with no
steps is a single turn, exactly the pre-rebuild behaviour.

The run's events are the agent's, plus three:

| Event | Meaning |
| --- | --- |
| `plan` | the steps and tools, before anything runs |
| `step` | `running` / `done` / `failed` (with a reason), by index |
| `result` | `changes`: what was written, each with an `undo` |

`undo` is a **tool call**: `{"tool": "edit_note", "arguments": {…}}` captured
*before* the write, which the UI hands back to `POST /chat/tools/execute`,
the same path the confirm button uses. It is popped out of the result before
the result reaches the model, because everything left in a tool result is
resent on every later round.

The agent loop (`ai/agent.py`) streams: it calls `chat_tools_stream`, so the
model's prose reaches the user as it is written rather than arriving in one
block when the turn ends. Text that might turn out to be a tool call written
as prose is gated until it is clearly not one, so it is executed rather than
displayed. The UI renders the run as an ordered timeline (thinking, tool
calls and prose in the order they happened) and persists it with the turn.

## 8. Data model

SQLite via SQLAlchemy 2.0 (`core/database.py`). Main tables:

- **users**: single-user unlock (one bcrypt-hashed password). Exactly one
  row: separate notebooks are separate `TESSELLATE_DATA_DIR`s, not separate
  accounts. The password can be changed from Settings → Account & security, which
  re-wraps the vault key onto the new password *before* replacing the hash:
  the other order would strand every private note.
- **vault**: the data key for private notes, wrapped with a key derived from
  the password, and optionally a second time by a recovery key (`recovery_salt`,
  `recovery_wrapped_dek`, `recovery_created_at`; the key itself is never
  stored). This is why a forgotten password without the recovery key loses
  private notes and only private notes: everything else is plain rows. The lock
  screen's "Forgot your password?" (`/auth/recover`, `/auth/reset`, this
  computer only) and `--reset-password` share `core/password_reset.py`, which
  clears the credential; both say exactly what that costs before it runs.
- **categories**: named buckets; each has an embedding centroid used for the
  janitor's cheap-match path, and a nullable `colour` (a palette key or
  `#rrggbb`; NULL is the name-based automatic colour).
- **entries**: the notes themselves: `content`, `category_id`, JSON `tags`,
  `ai_confidence` (0–100), `access_count`, `parent_id` (train-of-thought
  threads), `pinned`, `user_filed` (user chose the category → janitor keeps
  hands off), timestamps, and soft-delete (`is_deleted` / `deleted_at`).
  Also on an entry: `suggested_tags` and `discarded_tags` (JSON lists):
  the tags filing offered, shown on the card as "+ tag", and the ones a
  person refused so no later pass offers them again on that note (`_keep_suggestions`
  in `routes_entries.py` fills the first at filing: the model's tag pass when
  the model filed the note, otherwise `ai/lexical_filing.suggest_tags`, which
  only ever offers tags the person already uses); and `edited_at`, which moves only when a person changes the
  text, tags or category (`updated_at` also moves on every open, so it
  cannot sort by "recently edited").
- **entry_links**: user- or AI-made connections between two entries (the graph).
  **Privacy of a link:** `reason` is free text about the two notes, so on a link
  with a private end it is stored encrypted (`mmenc1:`, the note's own key) and
  left out of the activity log's text; the column type (`database.LinkReason`)
  decrypts on load while the vault is open and reads `None` while it is locked,
  so no reader learns about ciphertext. `set_private` seals the reasons already
  on a note's links and redacts the old "linked" rows, un-private restores them
  unless the other end is still private, and `/rotate-vault-key` moves them with
  the notes (`manager.rekey_private_extras`, which also moves the version
  snapshots and event payloads, left under the old key before).
  **Decision, 2026-10-04: a private note's tags stay in the clear**, in
  `entries.tags` and in `entry_revisions.tags` (a copy of the same list). The
  note list, the filter chips and the tag cloud show a private note's tags by
  design, so hiding them in the database would hide nothing a reader of the
  app cannot already see and would break tag filtering; what the privacy
  promises cover is the *text*, the embedding and the dates. Anyone who wants a
  tag kept out should not put it on a private note. `tests/test_private_link_reason.py`
  pins this.
- **derived_facts**: what the app worked out about a note rather than what
  anybody wrote (`ai/facts.py`, WORLD_CLASS_PLAN 15 I1 and I9): a claim the
  note makes or a question it leaves open, with the span it came from, the
  model that decided (or `local`), a confidence, and the lifecycle that
  makes the model's judgement reversible: `edited_by_user` plus
  `original_text` (a re-run never overwrites a correction, Reset restores
  the model's words) and `deleted_at` as a tombstone (a deleted fact is
  never re-derived). Read and corrected through `/learned`; written by the
  night pass, which is a task in `ai/autonomous.py` and `POST /night/run`.
- **whiteboard_nodes / whiteboard_sketches**: a note card, or a freehand
  stroke list, placed at an `(x, y, z)` on a board (§39C). `board_id` points at
  an *entry*, so a board is a note and inherits searching, tagging and filing;
  `NULL` is the unnamed scratch board. Deleting an entry leaves its cards for the
  background pass to sweep (`autonomous.clean_orphaned_board_cards`), the way
  `embeddings.clean_orphaned_vectors` sweeps vectors. A board's own shapes and
  connectors are `whiteboard_objects`, and its saved pieces `board_libraries`,
  `board_library_items` and `board_library_marks`.
- **user_preferences**: the memory stream (§39B): standing instructions the
  model wrote for itself with `save_user_preference`, replayed into its system
  prompt on every later turn. `active` exists so one can be switched off, and
  Settings → What it remembers lists the rows, says how much of them reaches the
  model, and lets each be edited, switched off or forgotten (`/memory`).
- **embeddings**: per-entry vectors, stored as raw `float32` bytes.
- **attachments**: uploaded files, kept in `data/uploads/`.
- **conversations**: saved chat threads. Messages are one JSON column of flat
  user/assistant pairs. An assistant message carries `content` *and* `steps`:
  the run as an ordered timeline (thinking, tool calls, prose). `steps` is what
  the client replays when a chat is reopened; `content` is the flattened text
  used for copying and for the history sent with the next question. **Anything
  that edits an answer has to update both**, or the edit is invisible the
  moment the chat is reopened.
- **entry_dates**: what a note's relative time phrases resolved to when it
  was written ("next Friday" → 2026-08-07), with the phrase kept beside the
  date because the resolution is a rule, not a fact. Filled by
  `entry/timewords.py` at capture and on every content edit, deterministic
  regexes rather than a model call, because this runs on every save including
  when Ollama is off, and best-effort because a note must save even if it
  fails. **Anything derived from a note's text and stored in the clear has to
  be cleared when the note is made private**, exactly like its embedding:
  "the appointment is tomorrow" plus a date is most of the note.
- **entry_revisions**: edit history for notes. Documents have no equivalent
  yet, which is why the AI document edit overwrites on accept.
- **documents**: long-form markdown, separate from notes.
- **document_links**: which notes a document draws on. Its own table because
  the relationship is many-to-many and neither side owns the other: detaching
  removes a connection, never a note. `manager.link_document` /
  `unlink_document` / `documents_for_entry` / `entries_for_document` are the
  only four functions that know how the two are joined, so the note side and
  the document side cannot drift apart. A note can be attached as it is saved
  (`document_ids` on `POST /entries`), which is the point: the connection is
  obvious while you are writing and forgotten by the time the note is in a
  list.
- **reminders**: lightweight reminders the agent can set. Stored UTC-aware:
  SQLite drops timezones and JavaScript parses a naive date-time as *local*,
  which read as a reminder being hours overdue the moment it was set.
- **audit_log**: every meaningful action, shown in the Library's Activity view.
- **spaces**: the notebooks inside the notebook; a note, document, chat and tag
  belongs to one (`workspace_scoped_models`).
- **entities · entity_mentions · relation_types · entry_properties · note_types**:
  the entity layer, kinds of link, and a note's properties and types (the
  knowledge-graph plan, KG3 to KG5).
- **ask_turns · page_reads · document_ai_edits · document_revisions ·
  note_scores · tensions · night_runs · media_uploads · chunk_vectors**: the Ask
  tab's history, the OCR workspace's page reads, a document's AI edits and its
  revisions, what the night pass computed, and the upload and paragraph-vector
  indexes.
- **job_runs**: one row per *kind* of job (not per run): `kind` (primary
  key), `started_at`, `finished_at`, `status` (running, ok, failed,
  cancelled), a one-line `result` or `error`, and `duration_ms`. Written
  only through `core/jobruns.job_run(kind)` from the search rebuild, the
  embeddings backfill, backups (manual and daily), the duplicate scan,
  imports, the night shift, the autonomous pass, resurfacing, link reasons
  and the other kinds in `jobruns.KINDS`; read by `GET /jobs/last-runs`.
  A bookkeeping failure never fails the job. `core/taskhistory.py` is the
  other half: what *stopped* since this process started, in memory.
- **jobs** (WORLD_CLASS_PLAN B2): one row per queued piece of pool work
  whose kind has a named handler in `core/jobstore.HANDLERS` (OCR,
  captions, the vision reads, document reads, filing): `kind`, JSON
  `payload` (never code), `state` (queued, running, done, failed,
  cancelled), `attempts`, and the lease (`owner`, `lease_until`,
  `heartbeat`). Launch resumes queued rows and running rows whose lease
  lapsed, at most three tries each; finished rows are pruned after a week.
- **bookmarks** carry `is_read` (a saved link you have been through).
  **entry_bookmarks** and **document_bookmarks** are the plain join rows that
  let a note or a document reference one.
- **entry_opens**: how often each note is opened, a row per note per day
  (`entry/opens.py`), which is what "most opened this month" reads.

**Migrations:** `database.py` runs an additive auto-migrator at startup: new
columns are added to existing databases in place. You never delete your data to
upgrade. A new table (like `job_runs`) is made by `create_all`. Alembic
(`migrations/versions/`) sits behind that for a rename or a drop: a database
with no `alembic_version` is stamped to head, one already stamped is upgraded.
One linear chain, a single head: `8a8a14407cc0` (baseline) → `b2f1c9d4e7a3`
(audit actor and payload) → `c7e4a1f60b58` (audit entity index) →
`d3b7c2a91e45` (ask turn grounding) → `e6f2a9c4b1d7` (`entries.edited_at`) →
`e5a9d1c3b7f2` (`categories.colour`) → `f4c8a2d6b1e9` (`bookmarks.is_read`) →
`a7d3e9c1f5b4` (link origin) → `b8e4f2a6c9d1` (entity kinds and aliases) →
`c3f7a9e2d5b8` (relation types and link properties) → `d9b2e6f4a1c7` (note
properties and types) → `e5a1c8f3b7d2` (locked board items) → `f3c7a9e1d5b8`
(board comments) → `a7d3e9c1f5b2` (`entries.client_key`) → `b7e3d1f9a2c4`
(the board library) → `a4c9e2f7b1d3` (`reminders.document_id`) → `b7e3d1a9c5f2`
(the bin for documents and reminders) → `c2f8a6d4e9b1` (`entry_opens`) →
**`b4e8d2a6f1c9`** (`entries.map_topic`, the head). `tests/test_alembic_baseline.py`
holds it; the stamp step is skipped under pytest.

### Why SQLite holds the notes (a decision, with its limits)

Asked directly, more than once: "why is storing in an sqlite database the
best way to store notes?" Written down here so it is answered in one place
rather than re-argued. **The decision stands, and this is why.**

What SQLite actually buys *this* app, which is a single-user, 100% offline
notebook on somebody's own machine:

- **One file to back up, move or lose.** `memorymap.db` is the notebook.
  `core/backup.py` copies it with SQLite's own backup API while the app is
  running, and a restore is one `os.replace`. Notes as loose files on disk
  would make a backup a directory walk and a restore a merge.
- **No server, no daemon, no port.** SQLite is a library. There is nothing
  to install, nothing to start before the app starts, and nothing running
  when the app is not (which is the other half of the same question, below).
  Postgres or MySQL would each add a service a person has to have working
  before they can write a note down.
- **Transactions, which are what "no silent loss" is built on.** A note, its
  tags, its links and its search-index rows land together or not at all.
  This is not theoretical here: it is what made the full-disk behaviour
  (INBOX 266, item 6) a clean refusal instead of a half-written notebook.
- **Search is in the same file.** `entries_fts` and `search_index` are FTS5
  virtual tables with bm25 ranking and a porter stemmer
  (`search/engine.py`, `search/index.py`). A notes-as-files design needs a
  separate index (Lucene, Tantivy, a vector store) that has to be kept in
  step with the files and rebuilt when it drifts. Here the index is written
  by an `after_flush` hook inside the same transaction as the write, so it
  cannot drift.
- **The numbers say size is not the problem.** Measured with
  `scripts/scale_test.py`: a real 50,000-note database is **12 MB**, and
  ~**88 MB** re-priced at a 384-dimension embedding, about **1.8 KB per
  note** including content, tags, metadata and vector. That extrapolates to
  **~350 MB at 200,000 notes**. Attachments (`data/uploads/`) sit outside
  this and are bounded by what the person attaches, not by the schema.

**Where it would stop being right**, which is the part a decision needs to
be worth writing down:

- **Concurrent writers.** SQLite takes one writer at a time. This app runs
  one process on purpose (see "One process, and why more is not an option"),
  and WAL mode lets readers carry on during a write, so it does not bite
  here. A multi-user server would change the answer.
- **Multi-device sync.** Two machines editing one SQLite file over a synced
  folder is a corruption story, not a sync story. If Tessellate ever syncs,
  the answer is a sync protocol over the row history, not a different
  database; nothing about SQLite is what blocks it.
- **A notebook far past the sizes above**, or a vector search that has to
  stay fast at millions of embeddings, where a purpose-built vector index
  would beat a linear scan over the `embeddings` table. That is a new index
  beside SQLite, not a move off it.

**And the shape the question came wrapped in: "things like containers are
spun up as needed like serverless cloud architecture."** That is the right
instinct for the wrong machine. Serverless exists to stop paying for idle
capacity in somebody else's data centre, and it buys that with a network
hop and a cold start. This app's promise is that it works with no network at
all, on one computer, with the model on the same machine; there is no meter
running, nothing to bill, and a cold start would be a delay added to writing
a note down. The local equivalent of "spin it up when needed" is what the
app already does: nothing runs on a timer that could be woken by an event,
the heavy pieces (the embedding model, OCR, SearXNG) load lazily on first
use rather than at boot, and what is left at rest is measured in the section
named next.

### Storage headroom, measured not guessed

Asked directly whether storage becomes a problem for a notebook that grows
for years. Measured with `scripts/scale_test.py` (roadmap ANALYSIS.md §34,
item 2) rather than estimated: a real 50,000-note SQLite file, checkpointed
out of WAL before measuring, was **12MB**: its `embeddings` table is the
only part that scales with vector size, and this fixture's vectors are 4
floats (16 bytes) rather than a real backend's 384–1024 dims. Re-priced at a
common local model's 384 dims (1536 bytes/vector), the same 50,000 notes come
to **~88MB**, or **~1.8KB per note** including its content, tags and
metadata. Extrapolated linearly (`entries`/`embeddings` are the only tables
that grow with note count, and both are simple fixed-width-ish rows, no
per-note table fan-out) that's **~350MB at 200,000 notes**, comfortably
inside "a notebook nobody will ever actually finish filling."

**What doesn't fit this rate, and isn't bounded by it:**

- **Attachments** (`data/uploads/`): arbitrary files, kept whole, with no
  cap and no relationship to note count. A notebook with a handful of large
  PDFs can outweigh 200,000 notes' worth of text easily; this is a
  per-attachment decision the user makes, not something the schema can
  budget for.
- **`entry_revisions`**: one row per edit, not per note. A note edited a
  hundred times costs a hundred times what one written once does; nothing
  currently prunes old revisions.
- **The `audit_log`**: one row per meaningful action, unbounded, growing
  with *usage* over time rather than with notebook size: a notebook used
  daily for years accumulates this independently of how many notes are in
  it.

None of the three above were sized in this pass, they are flagged, not
measured, because none of them is proportional to note count the way
`entries`/`embeddings` are, so a single "bytes per note" figure would
misrepresent them. Worth a dedicated look if either is ever reported as
actually large in practice; nothing today prunes `entry_revisions` or
`audit_log`, and neither has surfaced as a real complaint yet.

## 8b. Anything that leaves the machine

One module, `search/websearch.py`, owns every request made for a web search or
a page read, and it has three rules that are easy to break by accident. All
three have already been broken once. The other places that reach the network
(model downloads, optional packages, the update check) are listed in
[PRIVACY.md](PRIVACY.md), and `core/egress.py` records every connection the
process makes for Settings, Privacy, so a new one cannot skip the record.

**Which engine answers is the user's choice, read in one place.** The
`search_provider` preference is `auto` | `searxng` | `duckduckgo`
(`websearch.PROVIDERS`). `auto` tries SearXNG and falls back; **`searxng`
does not fall back**: reporting a failure is the point, because silently
re-routing to DuckDuckGo defeats running your own instance. Both callers (the
`/websearch` route and the agent's `web_search` tool) read it through
`websearch.settings_from(config)`. Two readers is how the tool ended up
honouring a different setting from the UI.

**Check an address and then connect to that address, not to the name.**
`_searxng_target` and `_pin_url` both resolve once, validate, and hand
`requests` an **IP literal** with the hostname in a `Host` header (and, for
HTTPS, `_PinnedAdapter` to keep SNI and certificate verification intact).
Resolving to check and resolving again to connect leaves a DNS-rebinding
window between the two. The reader path was fixed for this; the SearXNG search
path was not, and kept the hole for months while the *probe* beside it was
pinned correctly.

**A redirect is a new request.** `_get_external` follows hops by hand with
`allow_redirects=False`, re-checking each one, because `allow_redirects=True`
resolves the next hop inside `requests` where no guard can see it, and
"302 → http://127.0.0.1/" walks straight past a check on the first URL.

A configured SearXNG must resolve to this machine or the local network, and
**every** address it resolves to must, not merely one of them.

`search/searxng_manager.py` can install, start and stop an instance. Its
output goes to `data/searxng/searxng.log`: never `DEVNULL`, which is what
made a failed start unexplainable and reduced the error message to a guess
about the port.

Two things in there are Windows-specific and both were wrong in the same way,
a POSIX idiom that means something else entirely on Windows:

- **`os.kill(pid, 0)` does not ask a question on Windows, it terminates the
  process.** Any signal other than `CTRL_C_EVENT`/`CTRL_BREAK_EVENT` is passed
  to `TerminateProcess`, so the liveness check inside `_source_state` (which
  `status()` calls, which the settings screen polls every three seconds)
  killed the instance seconds after starting it and then reported that it
  "started but never answered". `_alive` now goes through
  `OpenProcess`/`GetExitCodeProcess` on Windows and only signals on POSIX.
- **`shutil.rmtree(..., ignore_errors=True)` cannot delete a git checkout on
  Windows**, because git marks `.git/objects` read-only. It deleted everything
  writable, left the folder standing, and reported success, after which
  `data/searxng/src` existed but was no longer a Python project, the installer
  skipped the download because the folder was there, and pip said *"does not
  appear to be a Python project"* about a path the user had never heard of.
  `_remove_tree` clears the read-only bit and retries, moves the tree aside if
  it still can't delete it, and reports what survived instead of pretending.

The rule underneath both: **a folder existing is not the question.**
`is_checkout()` asks whether there is a `setup.py` or a `pyproject.toml` in
it, and installing, starting and `source_installed()` all ask that rather than
`.exists()`. `install_source` also verifies `import searx` in the new venv
before calling the install done, because pip exiting 0 and SearXNG being
runnable are different claims.

**How SearXNG is installed, and why it looks so indirect.** Three separate
things each rule out the obvious approach, and all three were found by running
it rather than by reading:

1. **`git clone` cannot work on Windows, ever.** Four files in the repository
   have a colon in the name (`…/searxng.conf:socket` and three like it). A
   colon separates a drive letter, so git fetches every object and then dies:
   *"fatal: unable to checkout working tree"*, leaving the half-written
   folder that caused the error above. `pip install <tarball-url>` fails the
   same way, because pip unpacks the same files. So the archive is downloaded
   and unpacked *here*, skipping members this filesystem can't hold (they are
   nginx/uwsgi deployment templates, nothing the app runs) and members that
   would escape the directory.
2. **`pip install -e .` cannot work anywhere.** SearXNG's `setup.py` imports
   `searx` to read its version, and `searx/__init__.py` imports `msgspec`,
   which does not exist in pip's isolated build environment. It fails with
   `ModuleNotFoundError` before declaring a single requirement. So
   `requirements.txt` is installed first and the package is then built with
   `--no-build-isolation`, which is what SearXNG's own `manage` script does.
3. **The generated `settings.yml` turns off `tracker_url_remover`.** That
   plugin downloads a rules file from `rules1.clearurls.xyz` *during startup*
   and does not catch a failure, so an offline or proxied machine loses the
   process before it binds the port, "started but never answered" again.
   `websearch.strip_tracking` already does that job locally.

Verified end to end in this sandbox except the download itself (the proxy
blocks the URL): the archive unpacks to a real tree, installs, starts, serves
its JSON API, and `websearch.probe_searxng` returns True against it.

## 9. AI stack

- **Chat model:** any model installed in **[Ollama](https://ollama.com)**
  (default `llama3.2`). Talked to over the local REST API via
  `ai/ollama_client.py`. Used by the janitor, librarian, and agent.
- **Embeddings:** default `BAAI/bge-small-en-v1.5` via `fastembed` (its ONNX
  build, `Qdrant/bge-small-en-v1.5-onnx-Q`, downloaded after a yes). **Nothing user-facing may hard-code that
  name**: it was `all-MiniLM-L6-v2` once, and the Models screen went on
  saying so long after it changed, so the only way to find out what was
  really running was to watch it download in the log. Ask
  `EmbeddingService.active_model()`, which the status endpoint exposes as
  `active_embedding_model`. Optionally switch the backend to an
  Ollama embedding model; notes re-index automatically with a progress bar.
- **Voice (optional):** local Whisper via `faster-whisper` for the 🎙 buttons.
- **Other backends:** `ai/openai_client.py` speaks the OpenAI dialect for LM
  Studio, llama.cpp's `llama-server`, Jan and vLLM, and `ai/needle_provider.py`
  picks tools with a small built-in model when no server is running. Reading
  text in images and scanned PDFs goes through the Reading text model (a
  dedicated OCR model, else a vision model); see `ai/vision_ocr.py`.
- **Warm-up:** embeddings load in a background thread at startup so the first
  request isn't slow; the status bar tracks *ready / warming up / rebuilding
  index / off.*

Everything AI-related is designed to be *absent*: the app is fully usable with
Ollama stopped and no optional extras installed.

## 10. Frontend

A single-page app in **vanilla HTML/CSS/JS: no framework, no build step.**
Served as static files by the same FastAPI server (so no CORS is needed). It
is also a **PWA** (`manifest.webmanifest` + `sw.js`) with a mobile pass, a
command palette (Ctrl/Cmd-K), a graph of the notebook in four layouts: a
force-directed **web**, a **tree** (notebook → category → note, replies
branching off the note they answer), a **radial tree** and an **arc**
diagram, drawn with D3
vendored locally in `frontend/vendor/`, and a sketch pad (p5, also vendored,
loaded on demand by `ensureP5` the first time something draws). No asset
is ever loaded from a CDN, consistent with the offline-first rule. The
JavaScript is split by surface (`dashboard.js`, `timeline.js`,
`library.js`, `documents.js`, `graph.js`, `whiteboard.js`, `settings.js`); `app.js`
and the 26 files after it hold the shell and everything shared, cut on
2026-09-26 from one 50,000-line file into contiguous ranges kept in the old
order, so a file may call into the ones above it while the page loads and
never into one below (`tests/test_frontend_load_order.py`; tests read the 27
as one text through `tests/_app_js.py`). The two biggest lazy surfaces are split
further by concern: `documents-code.js` and `documents-prose.js` hold the
document editor's code and prose tools, and `whiteboard-map.js` the mind map
layer; each loads in the Library bundle *before* the file it came out of
(`documents.js`, `whiteboard.js`), because its own top level reads nothing from
that file while that file's top-level wiring names its functions (`LAZY_MODULES` in
`app.js`). Every local CSS and JS URL carries
`?v=<version>-<hash of that file>`, spliced into the served page, so no
browser or desktop window can keep a stale file and an unchanged one stays
cached across launches; lazy scripts and workers read their stamps from the
page's `<meta name="asset-stamps">`. What is served has its comments
stripped (`api/asset_strip.py`); the files on disk keep them
(`RevalidatedStatic` in `api/app.py`).

### The scripts, their order, and the one scope they share

A hundred and seven JavaScript files in `frontend/js/`, in five kinds (38 load at boot; `d3` is fetched from `vendor/` with the Graph bundle, not at boot; checked 2026-10-06):

| Kind | Files | Loaded |
| --- | --- | --- |
| Before first paint | `boot-guard.js`, `theme-boot.js` | in `<head>`, so the theme and the boot-failure guard apply before anything draws |
| The app's own code | `app.js`, `prefs.js`, `store.js`, `note-cards.js`, `menus.js`, `lightbox.js`, `selection.js`, `notes-list.js`, `capture-ask.js`, `chat.js`, `chat-agent.js`, `chat-attach.js`, `sheets-selects.js`, `skills.js`, `shell-reminders.js`, `markdown.js`, `navigation.js`, `router.js`, `settings-panes.js`, `media.js`, `status.js`, `ai-tools.js`, `phone-shell.js`, `wiring.js`, `settings-wiring.js`, `spaces-find.js`, `agent-activity.js` | at the end of `<body>`, in this order |
| The boot surfaces | `avatars.js`, `atlas.js`, `rich-picker.js`, `editor.js`, `dashboard.js`, `timeline.js`, `palette.js`, `bg-art.js`, `settings.js` | straight after, in this order |
| Lazy bundles | `graph.js` and `graph-canvas.js` (the Graph tab); `undo-store.js`, `documents-code.js`, `documents-prose.js`, `documents.js`, `margin-reader.js`, `whiteboard-map.js`, `whiteboard.js`, `whiteboard-commands.js`, `whiteboard-library.js`, `whiteboard-format.js`, `whiteboard-interchange.js`, `library.js` (Library and Documents) | on the first visit to the tab, by `ensureModule` from `LAZY_MODULES` in `app.js` |
| Lazy pieces | one entry each in `LAZY_MODULES`: `panel-movable.js` (`panelMovable`, with `panel-movable-lazy.css`), `lightbox-view.js`, `edit-conflict.js`, `categories-panel.js`, `tag-manager.js`, `chip-menus.js`, `note-history.js`, `ask-history.js`, `settings-data.js`, `settings-find.js` + `settings-models.js` (`settingsUi`), `tag-suggest.js`, `attachment-actions.js`, `ocr-engine.js`, `quick-note.js`, `field-clear.js`, `assistant-avatar.js`, `quick-access.js`, `notes-rail-spy.js`, `dash-boards.js`, `suggestions-inbox.js` + `entity-page.js` + `link-types.js` + `note-properties.js` (`inbox`), `model-bench.js`, `web-clip.js`, `app-import.js`, `usage-ledger.js`, and (2026-10-05) `reveal-targets.js`, `onboarding.js`, `update-dialogs.js`, `app-palette.js`, `note-panels.js` + `note-edit-panels.js` (`notePanels`), `attach-to.js`, `settings-controls.js` (no entry points: `openSettingsModal` awaits it on the first open), and, from the boot-budget moves, `tour.js` (the guided tour, when one starts or Settings, Help opens), `icon-picker.js` (the one emoji and icon picker), `nav-history.js` (the Back and Forward list's rows), `settings-packages.js`, `help-chat.js` (the Guide), `chord-guide.js`, `batch-space.js`, `note-templates.js`, `companion-menu.js`, `vault-unlock.js`, `pick-row.js`, `drag-edge.js`, `atlas-life.js` and `atlas-motion.js`, `ask-chart.js` (with `ask-history.js`), and `whiteboard-history.js` (with the boards) | on first use through `LAZY_ENTRY_POINTS`, to keep the boot scripts under their gzip budget; `quick-note.js` is fetched a few seconds after boot, because its outbox is for the moment the server is gone and a script cannot be fetched then |

Plus five that are not scripts of the main page: `sw.js` (the service worker),
`graph-worker.js` and `harper-worker.js` (web workers for the graph's layout
and the grammar checker), and `capture.js` and `clip.js` (the scripts of
`capture.html` and `clip.html`).

**Every one is a classic script, not a module, and they share one global
scope.** A top-level `function` or `const` in any of them is a global the
others can name, which is how `settings.js` calls `renderEmblem` from
`phone-shell.js` and how a Playwright `page.evaluate` can call `switchTab`. There
are no imports and nothing to resolve: the browser runs the files in the
order `index.html` lists them, one after the other, each to its end before
the next begins.

**Load order is therefore the one rule, and it has two halves.**

1. *Inside a function, anything goes.* A click handler, a renderer or a
   timer runs after every file has loaded, so it may call a function from
   any file, earlier or later.
2. *At load, only upwards.* A statement at a file's top level (a
   `$("x").addEventListener(...)`, an `init...()` call, a `const` built by
   calling something) runs the moment the browser reaches it, so it may use
   only what the files above it, and the lines above it in its own file,
   have declared. A `function` declaration is hoisted within its own file
   only; a `const` or `let` is not hoisted at all (reading one early is
   "Cannot access X before initialization", and one in a later file is
   simply "X is not defined"). A top-level throw stops the rest of that one
   file, not the page, so a half-booted app is the symptom to look for.

The two calls that start the app, `initNotesSubtabs()` and `initAuth()`, are
the last lines of `spaces-find.js` for that reason: they reach functions
declared across the whole app, and `initAuth`'s answer can arrive between
two files. A lazy bundle's entry points are reachable before the bundle
exists through `LAZY_ENTRY_POINTS` in `app.js`: a stand-in on `window`
that loads the bundle and then calls the real function. A boot surface that
calls into a later one guards the call with `typeof`.

**What holds the rule.** `tests/test_frontend_load_order.py` reads
`index.html`'s order and fails on a top-level call into a later file, on a
top-level read of a later file's constant, and on a lazy name read at load
with no stand-in; `tests/test_lazy_bundle_calls.py` covers the lazy bundles.
`scratchpad/appjs-map.js --check FROM TO [AFTER]` answers the same question
for a range of lines before it moves. The app's own code was one 50,000-line
`app.js` until 0.3.3; it was cut into the 27 files above as contiguous
ranges in their old order, so every reference that was backward stayed
backward (`docs/roadmap/archive/agent-remaining/appjs-split.md`). A test
that means "the app's code" reads all of them as one text through
`tests/_app_js.py`. To find a function's file:
`grep -n "^function name" frontend/js/*.js`.

### Driving it in a browser

The test suite cannot see any of this, so verify UI work by running the app:
`bash scratchpad/ui-sweeps/serve.sh <port> <data dir>` starts one, and the
sweeps in `scratchpad/ui-sweeps/` (`lib.js` boots and logs in; `errors.js`,
`contrast.js`, `docks.js`, `touch.js` are the standing gates) drive it with
the Node Playwright under `/opt/node22` and the Chromium under
`/opt/pw-browsers`. CLAUDE.md section 5 lists the traps. Launch a context
with `service_workers="block"`, or `sw.js` will serve a cached `app.js`
and your change will not be in the page you are looking at.

Top-level functions in `app.js` and the files after it are plain globals, so a Playwright
`page.evaluate` can call `switchTab`, `applyThemePreset` or `renderEmbeddingPicker`
directly. Asserting on measured geometry (`scrollWidth - clientWidth`, a
focused element's `offsetParent`) catches far more than a screenshot.

### Invariants worth knowing

1. **The Notes tab has sub-tabs** (`browse`, `capture`, `writing-room`, `ask` and
   `questions`: Your notes, Capture, Writing room, Ask and Questions) and
   remembers the last one in `localStorage`. Anything that focuses or scrolls to an
   element there must call `showNotesSection(...)` first: focusing inside a
   `display: none` section silently does nothing, and the control reads as
   dead. This has caused the same bug four separate times.
2. **CSS automatic minimum sizing is the usual cause of a wide page.** A grid
   track of `1fr` and a flex item of `min-width: auto` both refuse to shrink
   below their content, so one wide code block or table widens its column, the
   page, and every paragraph beside it. `overflow-x: auto` on the child cannot
   take effect until every ancestor has an explicit floor: `minmax(0, 1fr)`
   on the track *and* `min-width: 0` on the item.
3. **Later CSS at equal specificity silently wins.** A media query that sets
   `flex` is undone by a base rule declaring `flex` further down the file. The
   header's tabs were pinned at a rigid 579px this way for a long time, and the
   block that was supposed to free them looked perfectly correct.
4. **Inline styles beat stylesheets, which is how colour layering works.** A
   palette sets `--accent` from a `[data-palette]` rule; an explicitly chosen
   accent is written as an inline custom property so it wins. Two rules of
   equal specificity would otherwise be decided by source order.
5. **The header degrades in a fixed order** as the window narrows: wordmark,
   then tab padding, then the tabs scroll. Its buttons
   never shrink. Breakpoints here are measured, not guessed: the desktop
   shell's window is 1200x800, which is less viewport than it sounds on a
   scaled display.
6. **`prefers-reduced-motion` disables animation**, so any animation carrying
   *meaning* needs a still fallback or it reads as a rendering fault.
7. **p5 measures a canvas as zero inside a `display: none` tab.** Anything
   using `renderEmblem` has to be drawn in its own tab's render, not at
   startup, which is also what makes it redraw when a theme change moves the
   accent.
8. **Note text is user content and is never parsed as markup.** Everything is
   built with `createElement` / `textContent`. `renderNoteText` layers
   `[[wiki links]]`, then `renderInlineMarkdown` (bold, italic, `code`,
   strike, inline only, deliberately), then `highlightInto` for filter
   matches, and all three have to keep working through each other. Block
   markdown is *not* used in the note list: rendered headings and tables make
   it enormous. The dashboard's one-line previews strip the markers instead
   (`notePreviewText`), because a 70-character clip can land mid-tag.
9. **Appearance is three layers, read manual-first**: defaults →
   the chosen theme → your manual tweaks (`appearancePref`). That order is
   right for a tweak made *after* choosing a theme and wrong for every theme
   chosen after the tweak: one stored palette cancelled that part of each new
   theme, so themes "did nothing". `applyThemePreset(name, chosenByUser)`
   therefore clears the manual keys *that theme has an opinion about* when the
   user picks one, and no others. **A new appearance key needs a decision
   about which layer owns it**, or it silently joins the layer that outranks
   the theme.
10. **A graph layout is a set of rules about what a label needs**, not about
   what the panel has. `d3.tree().size([...])` divides the panel height by the
   leaf count, which gave a 29-note notebook eighteen pixels a row; `nodeSize`
   and panning is the fix. The radial rings **by depth** (`d3.tree`), not by
   `d3.cluster`'s height, or a category containing a thread sits a ring in
   from its siblings. `frameTree` frames from the canvas's measured `getBBox`
   rather than from node coordinates plus a padding guess, because the labels
   are what overflow. Assert on the labels' rotated corners, not their
   axis-aligned boxes: those overlap when diagonal text does not.
11. **Settings sections are three things that must agree**: an entry in
   `SETTINGS_SECTIONS`, a `<section id="settings-NAME">`, and a
   `<button data-section="NAME">` in the nav. Miss the first and the section
   never hides; miss the third and it is unreachable.

## 11. Configuration

A few knobs, all optional, via the environment or `.env` (copy from
`.env.example`). [INSTALL.md](INSTALL.md) has the full table; the ones that shape
the architecture:

- `TESSELLATE_DATA_DIR`: where the database, preferences, uploads, and backups
  live (default `data/` beside a source checkout; the per-user app folder for a
  packaged build, `core/config.py`'s `_default_data_dir`).
- `TESSELLATE_PORT` (default 8000) and `TESSELLATE_LAN_PORT` (default 8443, the
  HTTPS port other devices use when LAN mode is on; `core/netbind.py`).
- `OLLAMA_URL`: where the local Ollama server listens (default
  `http://localhost:11434`).
- `TESSELLATE_SEARXNG_PORT`: the port to run a managed SearXNG on (default
  8888). Rarely needed: `searxng_manager.choose_port()` already moves to
  8080/8081/8890/8899 when the wanted port is held by something that is not a
  SearXNG. A port *already answering as SearXNG* beats a free one: that is
  ours from a previous run, and moving would start a second copy beside it.

User-facing preferences (chat model, embedding backend, recycle-bin days, answer
style, optional AI profile, …) live in `data/preferences.json`, managed by
`ConfigManager` and edited from the Settings panes.

## 12. Testing & CI

- **Run locally:** `PYTHONPATH=src pytest -n auto` (about 1,400 files, 12,400+ tests,
  under nine minutes on four cores and about 25 serially). Uses a throwaway database and fakes every AI call
  (`tests/fakes.py` + `tests/conftest.py`), so it is fully offline. The
  routine local gate is `bash scripts/gate.sh --changed` (the lint set,
  `node --check`, ruff, and the tests that name the files you changed);
  `--staged` checks the index before a commit; the full suite runs in CI on
  every push and locally only at the end of a large piece of work.
- **Scanning the tree:** a test that reads many source files takes its list from `repo_files()` in `tests/_repo_files.py` (the checkout walked once per process, filtered per call by `suffixes`, `patterns`, `exclude_dirs`, `exclude_names`), never its own `rglob`; `Path.read_text` for files under `frontend/`, `src/`, `docs/` and `tests/` is cached in `tests/conftest.py`, so the scanners share one decoded copy.
- **The suite cannot see the UI.** Every layout and wiring bug fixed so far
  passed a fully green run: a header overflowing its own box by 215px, a
  button focusing an element inside a hidden section, an accent picker with no
  effect. Drive the app in a browser before believing a frontend change works;
  §10 says how.
- **Lint locally:** `ruff check .` (and, optionally, `ruff format` to tidy).
- **Evals against a real model, by hand only.** Every provider test in the
  suite runs against a fake transport, so nothing in `tests/` can say how a
  real small model answers a re-prompt. `scratchpad/llama-dev.sh` closes that
  gap for a developer who asks for it: `check` says what is present and
  downloads nothing, `fetch` downloads one small instruct GGUF outside the
  repository, `build` compiles `llama-server` from a llama.cpp checkout you
  name, and `serve` starts it and prints the two exports the evals read,
  `TESSELLATE_EVALS_URL` and `TESSELLATE_EVALS_MODEL`. With those set,
  `pytest -m evals tests/` runs the eval tests against that model; without
  them every eval is skipped, so the ordinary suite and CI never depend on a
  model, a binary or a network. Nothing in `tests/` imports the script and no
  mode of `scripts/gate.sh` calls it, which
  `tests/test_skills_evals.py::test_the_evals_seam_is_the_only_thing_that_reaches_the_runner`
  asserts rather than trusting.
- **CI** (`.github/workflows/ci.yml`): lint with ruff, then run the full test
  suite on Python 3.11 / 3.12 / 3.13, the tests that need the PDF rasteriser in
  their own job, and the Playwright smoke suite in `tests-e2e/`. No GPU, no
  Ollama, no models required. `package-check.yml` builds and smoke-tests the
  frozen Windows app and the installer before release day, and `release.yml`
  publishes them ([RELEASING.md](RELEASING.md)).
- **CodeQL** (`.github/workflows/codeql.yml`): static security analysis on push,
  PR, and weekly.
- **Dependabot** (`.github/dependabot.yml`): weekly dependency + Action bumps.

## 13. Running it

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt && pip install -e .
python -m tessellate            # → http://localhost:8000
python -m tessellate --desktop  # same app in its own window (needs pywebview)
```

On first run you choose a password (bcrypt-hashed, stays local). The launcher
scripts, the installers and the command-line options are in
[INSTALL.md](INSTALL.md); the [README](../README.md) tours each screen.

### What runs when nothing is happening

Asked directly, with the rest of the architecture question: "are things
running when they arent necessary and taking up extra compute?" Measured
rather than argued, on 2026-09-21, with `scratchpad/ui-sweeps/idle.js`
(requests and timer wakes per idle minute, visible and hidden) and
`scratchpad/ui-sweeps/idlecpu.js` (Chromium's own `TaskDuration` for the tab
and `/proc/<pid>` for the server, over three minutes of nothing).

**The server, with no browser attached at all, is asleep.** Sampled per
thread over 30 seconds: 0.04s of CPU on the main thread and zero on the
other 22, which is 0.13% of one core. Nothing here spins. The background
pieces are all blocked rather than polling: `core/jobs.py`'s workers sit on
a queue, `ai/autonomous.py`'s scheduler waits on a `threading.Event` with
its whole interval as the timeout (it used to wake 21,600 times a night to
check a flag), and the heavy pieces (the embedding model, Tesseract,
SearXNG) are not loaded until something asks for them.

**The cost is the open tab, and it is small but it was not nothing.** Every
waker, before and after, with its period:

| Waker | Period | Notes |
| --- | --- | --- |
| `refreshModelStatus` | 30s idle, doubling to 120s while the answer does not change; 1s while a job runs, 3s with Settings open, 120s hidden | Is the model runner up, which model, and any running job |
| `checkDueReminders` | 60s, visible or hidden | The one thing a background tab *should* keep doing |
| `refreshBackgroundTasks` | every other status tick when idle | Notices a job started somewhere else |
| `minuteTick` (three clocks) | on the minute | Was two 1s intervals and one 30s one |
| `libraryImagesPoll` | 6s, only while the Library's image gallery is the open sub-tab | Captioning runs on a background thread and has nothing to push with |

What was cut, and what it bought, measured on one server and one notebook
with only the frontend swapped:

- **Two HH:MM clocks ticking once a second.** They painted the string that
  was already on screen 59 times out of 60. `startMinuteTicker` (shell-reminders.js)
  schedules the next repaint on the wall-clock minute instead, which is both
  cheaper and more correct: the status bar's clock was a 30s interval, so it
  could show a minute that had already passed for up to half a minute.
  **Timer wakes in an idle visible minute: 124 before, 5 after.**
- **A status poll that asked twice a minute for ever.** It backs off to a
  two-minute ceiling while the answer is byte-identical, and drops straight
  back to 30s on any change, on returning to the tab, on opening Settings
  and on starting a job. Every one of those polls reaches Ollama, so an idle
  tab was waking the model runner 2,880 times a day to be told the same
  thing. **Requests in an idle visible minute: 4 before, 2 after**, which is
  WORLD_CLASS_PLAN section 10's gate for this row.

**The CPU numbers, on one machine, one server and one notebook, with only
the frontend swapped** (`idlecpu.js`, two rounds of two minutes each, the
tab's own `TaskDuration` plus the server's `utime+stime`):

| At rest, Dashboard open | Tab | Server | Total |
| --- | --- | --- | --- |
| Before | 5.71%, 5.80% | 0.31% | **6.01%, 6.11%** |
| After | 5.20%, 5.30% | 0.30%, 0.29% | **5.50%, 5.59%** |

**And the honest reading of that**: removing 119 of 124 wakes a minute was
worth about half a percentage point. Nearly all of what is left is one
thing, and parking the app on the Notes tab instead names it: **1.79% tab,
0.30% server, 2.09% total**. The difference is the Dashboard's emblem, a p5
sketch that draws at 24fps because it was asked to ("whenever the generated
p5.js node graph logo shows, make sure it is never static and always
rotating"). The five emblems that are *not* on screen were already stopped
with an `IntersectionObserver`; the one that is on screen is the decision,
not an oversight, and it is about 3.5 points of the 5.5. Worth knowing
before anyone goes looking for a leak: there is no leak, there is a
deliberate animation, and turning it down is a design choice rather than a
bug fix. **Since answered without turning it down:** the emblem is drawn
once and turned by a CSS rotation (`canvas.emblem-spin`), at the same
speed, so the compositor does the turning and no p5 loop runs for it at
all. Not re-measured with `top` since.

What was deliberately *not* cut: the 60-second reminder check, because a
reminder that waits for you to look at the tab is not a reminder, and the
Library gallery's 6-second poll, which only runs while that gallery is the
open sub-tab and exists because captioning finishes on a background thread
with no channel to announce itself on. The event stream that would replace
it is WORLD_CLASS_PLAN's B1, and it is a refactor rather than a fix.

### One process, and why more is not an option

**Tessellate runs with exactly one worker, and refuses to start with more.**
`core/deps.refuse_multiple_workers()` runs at the top of `create_app()` and
raises on `--workers N` (N > 1) or `WEB_CONCURRENCY`.

This is not caution: it is the direct consequence of §3's singletons. The
config, the database handle, the in-memory log buffer, the set of unlock
tokens and the handle on the SearXNG subprocess are all one-per-process,
which is correct and simple for one process and quietly wrong for two:

| With two workers | What you would actually see |
| --- | --- |
| Two log buffers | Settings → Logs shows roughly half of what happened |
| Two token sets | Unlocking works, then randomly 401s on the next request |
| Two SearXNG handles | Both workers think they own it; stop/reinstall fight |
| Two embedding warm-ups | The model loads twice, for twice the memory |

None of that fails loudly, which is exactly why it is refused rather than
warned about: it would present as flakiness and be debugged as a bug in the
app. `python -m tessellate` cannot hit this (it hands uvicorn an app object,
not an import string, and uvicorn cannot fork that); running `uvicorn` against
the factory directly can, and is the case the check exists for.

More workers is also not the lever for speed here. The slow paths are Ollama
and embedding. A deferred filing (`defer_filing`) runs both off the request
thread; a plain save and an edit still embed on the request (corrected
2026-10-05, audit ARCH-02: this line said both were always off it).

## 14. Where to look when you want to…

| I want to… | Start here |
| --- | --- |
| Change how notes are categorised | `src/tessellate/ai/janitor.py` |
| Change how questions are answered | `src/tessellate/ai/librarian.py` |
| Add/adjust an agent action | `src/tessellate/ai/tools/` (+ `agent.py`) |
| Add an API endpoint | the matching `src/tessellate/api/routes_*.py` |
| Add a database column | `src/tessellate/core/database.py` (+ auto-migrator) |
| Teach it a new time phrase | `entry/timewords.py`: one rule, one test row |
| Change search behaviour | `src/tessellate/search/search_manager.py` |
| Change the UI | `frontend/js/app.js` and the files after it (`grep -n "^function name" frontend/js/*.js` finds a function's file), `frontend/css/*.css` (read §10's invariants first) |
| Add a graph layout | `layoutHierarchy` in `graph.js` + an option in `#graph-layout`; d3's full v7 is vendored, so `tree`/`cluster`/`partition` are all there. Read §10 invariant 10 first: the readable-layout rules are not obvious |
| Add a theme or palette | `THEME_PRESETS` in `settings.js` + a `[data-palette]` block in `frontend/css/05-sidebars-themes.css` (where the curated palettes live); §10 invariant 9 for why a theme has to clear manual keys |
| Change what the Timeline plots | `api/routes_timeline.py`: a note sits at what it is *about* when it says so |
| Work out why a page scrolls sideways | §10 invariant 2: an ancestor with no `min-width: 0` |
| Change what a saved chat replays | `steps` in `routes_conversations.py`: not just `content` |
| Add a preference | `DEFAULT_PREFERENCES` in `core/config.py`, then `PreferencesBody` + `get_preferences()` in `routes_settings.py` |
| Add a Settings screen | §10 invariant 11: three places, all three needed |
| Change which search engine answers | `websearch.PROVIDERS` + `settings_from()`; never read the preference directly |
| Add an agent tool | `ai/tools/`, then run `tests/test_prompt_budget.py`: schemas are 77% of the per-round cost |
| Change what a skill can be | `ai/skills.py`: `normalise` is the one validator both the editor and `save_skill` go through |
| Add a built-in skill | `skills.BUILTIN_SKILLS`, not `app.js`; name its tools (§7b) |
| Log something a user or a website typed | `logbuffer.safe_value()` at the call site; `sanitise` only protects the in-app viewer |
| Work out why SearXNG won't start | `searxng/searxng.log` in the data folder, surfaced in Settings → Web search |
| Expose a tool to another program | `mcp_server.py`: it lists only non-destructive, enabled tools, so a new destructive tool needs no change there |
| Add a background job | `core/jobs.enqueue(kind, func, ...)` with a lane in `KIND_LANES`, never a `Thread` of its own; `api/routes_tasks.collect()` already draws what the pool holds, so the panel needs nothing |
| Show when a job last ran | wrap the job in `with jobruns.job_run("kind") as run:` (`core/jobruns.py`), set `run.result`, and add the kind to `jobruns.KINDS` for its wording; `GET /jobs/last-runs` and Settings → Background tasks (its Background jobs list) pick it up. Never write a `JobRun` row by hand |
| Change how a note is filed with no model | `ai/lexical_filing.py` (`suggest_categories`, `suggest_tags`); the janitor and `_keep_suggestions` in `routes_entries.py` call it |
| Change a Settings model card (size, fit, good for) | `ai/model_cards.py` `decorate`, with `core/hardware.py` for the memory figure |
| Change what happens when a note is saved with the server away | `frontend/js/quick-note.js` (the outbox, `client_key`) and `_already_delivered` in `routes_entries.py` |
| Add a lazily loaded script | a `LAZY_MODULES` entry in `app.js`, a stand-in in `LAZY_ENTRY_POINTS`, and its name in `LAZY_PIECES` in `tests/_app_js.py` |
| Add a kind to the Library | `api/routes_library.py`: one builder function, and `app.js` needs no change |
| Make something installable | `core/extras.py`'s allowlist, never a package name from a request. `unavailable` greys it out *and* refuses it server-side |
| Add an embedding model | `core/embedmodels.py`'s allowlist. The `org/name` → `models--org--name` flattening is the traversal defence, not formatting |
| Size something against the window | `--page-viewport` / `--page-sticky-h`, never a fresh `calc`. Three rules once wrote the same sum by hand and all three were wrong by the page's bottom padding |
| Add a test | `tests/`: copy an existing `test_*.py` and reuse the fakes |

---

*This document tracks the codebase: if you change the architecture, update it in
the same PR.*
