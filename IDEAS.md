# Ideas parking lot

Good ideas that are **out of scope right now** are written here instead of
built (build plan section 0: never expand scope mid-phase). The list is the
owner's own, tidied on 2026-10-05: grouped, spelling fixed, and checked against
the app.

**Check the app before building anything here.** Most of this list has been built
since it was written, and the common mistake in this project is rebuilding
something that exists (CLAUDE.md, section 1). The built items stay, with where
they live, because their wording is what a future session will search for.

- [Built](#built)
- [Partly built](#partly-built)
- [Filed as LEDGER rows](#filed-as-ledger-rows)
- [Where the rest stands](#where-the-rest-stands)
- [From the audits](#from-the-audits)

## Built

**Capture and the shell**

- Handle image and file uploads, with drag and drop: attachments, the Library's
  Images and Files views, captions, vision reads, Tesseract text and the OCR
  workspace.
- A guided setup on first install: the welcome card and the guided tour (Settings,
  Help), which walks through the real controls.
- A mini bar at the bottom with statuses and quick access to the command palette:
  the status bar at the foot of the window, and the palette on `Ctrl`/`Cmd`+`K`.
- Allow saving custom appearances and themes: thirteen themes and saved looks, in
  Settings, Appearance.
- Collapsible sidebars.
- Make Tessellate cross-platform: a Windows installer and a Linux package, and
  macOS from source.
- Package the application, and improve the Settings models page: the installers,
  and Settings, Models with fit badges and a model per feature.
- Improve start.bat: no console window to keep open, and a tray icon. The launcher
  has `--doctor`, `--logs` and `--shortcut`, and the desktop window has a tray menu
  with Open, View logs, Restart and Quit.
- A way to exit the app and quit the backend: Quit in the header, and Settings,
  Background tasks.
- An interface for managing the application (backend, console, update, packages,
  restart, health): Settings, Background tasks, Packages, Logs and About.
- Improve the console in settings and show all console messages: Settings, Logs.
- A way to run the application on a phone: a layout built for the phone, the
  Share to Tessellate action, and, for a phone on your own network, LAN mode over
  HTTPS (Settings, Account & security).
- The help area in settings has an ask-AI feature that knows the program's
  documentation: the Guide, and Ask Atlas about the app (`Ctrl`+`Shift`+`H`).
- A full security sweep: the audit of 2026-10-05 and its fixes are in the
  changelog under Security, and [`SECURITY.md`](SECURITY.md) states the model.
- Update the readme: rewritten on 2026-10-05, with every document in `docs/`.

**The AI**

- More tools, including managing categories (create, rename, merge, delete), and
  better agentic workflow: 65 tools, a visible plan, a confirm card for anything
  that changes or deletes.
- More skills, and a way to make new ones, including a full audit and clean-up of
  the notebook: 21 built-in skills (Notebook health check, Clean up my tags,
  Reorganise my categories, Fix my links, Find notes worth combining, Build a
  skill), and your own as Markdown files.
- Quick, normal and detailed modes for chat and agent: response presets.
- Reduce token usage in every AI interaction: the per-turn context budget, the
  small-model mode and schema compaction.
- Optimise outputs for what the current model can do: the small-model mode, and
  per-model sampling defaults.
- A nudge for the semantic search so "what did I save in the last two days" works:
  date-aware search operators and time travel over meaning.
- Reduce the cap on semantic search results, based on the model's context:
  `search_notes` scales its default result count with the model's window. The
  ceiling deliberately does not scale, because letting it do so meant a 128k model
  could pull 768 note previews into one tool result.
- Have the agent reachable from anywhere in the program: the popup agent
  (`Ctrl`+`Shift`+`A`) over every tab, and the agent activity monitor.
- Dynamically change models based on the task: background work uses the utility
  model so it does not tie up the chat model (`smart_model_routing_enabled`).
- Chat message metadata that survives a reload: the whole stats block is stored
  per turn, and every message says how full the model's window got.
- Make the notebook constellation regenerate on a light or dark change: it is
  rebuilt on every mode, accent and palette change, keeping the same arrangement.
- The background librarian: runs on an interval, tags, links and flags
  duplicates, off by default, never deletes. The category work (rename, merge,
  move) is done by the skills above.

**Notes, documents and boards**

- Expand and improve the sketches board, maybe a whiteboard tab: boards and mind
  maps in the Library's Boards & maps view, with shapes, connectors, an object
  library and mind maps.
- Better documents UI and usability, and make notes and documents two halves of a
  whole: the long-form editor, document links, backlinks and the Contents tree.
- A visual timeline: the Timeline tab with feed, table and scrubber.
- More dashboard widgets: the dashboard's widget set, including Boards & maps.

## Partly built

- **Agent asks for permission in chat and documents, with before-and-after
  comparison.** The confirm card exists for destructive and outside-text-triggered
  changes. A before-and-after comparison for every edit does not.
- **The agent controls the app on screen, with a visible border and a cancel.** The
  popup agent and the activity monitor exist. The monitor is fixed bottom-right
  rather than movable or dockable, and the agent does not drive the interface.
- **Dynamic model choice by task complexity.** Routing is by caller, not by how
  hard the task is.
- **Better agentic web search through chat.** `web_search` and `read_url` exist,
  with a SearXNG option. A research mode that plans several searches does not.

## Filed as LEDGER rows

These sixteen ideas are LEDGER rows L-world-class-172 to L-world-class-187
(`docs/roadmap/LEDGER.md`), where they are sized and worked in order.
## Where the rest stands

Checked against the app on 2026-11-14. Each idea is built, or has its place in
BACKLOG with the reason it waits.

- Manually group notes together, separate from the main sorting: BACKLOG §23
  (tags may already serve; a `collections` table if not).
- A note with more than one category: BACKLOG §23, the same entry.
- Compress notes and data on disk: BACKLOG, "Compressing the notebook on disk".
- Gravity and spread on the graph's other layouts: built (L-world-class-175,
  `tests/test_graph_physics_layouts_175.py`).
- A visual timeline drawn as a branching line with off-shoots: built
  (L-world-class-176, `tests/test_timeline_branch_176.py`).
- Settings pages on a narrow phone view: measured at 360 and 320 wide, 21
  sections, none cut off (L-world-class-177,
  `scratchpad/ui-sweeps/settings-phone-177.js`).
- Markdown in the dashboard's widgets: built (L-world-class-178,
  `tests/test_dash_widget_markdown_178.py`).
- Pie charts for the dashboard: built, the Category mix widget
  (L-world-class-179, `tests/test_dash_pie_179.py`).
- Different ways to sort chats: built (`#chat-sidebar-sort`: recent, most turns,
  most tokens, A to Z; pinned chats first). Grouping chats with an agent tool
  and a skill: BACKLOG, "Grouping saved chats".
- An agent's edit proposed as a suggestion you can accept: built in documents
  (`documents-ai.js`, a diff with a box per change, then Replace, Insert or
  Remove) and in chat (a tool that writes asks first and is parked until you
  confirm).
- An in-built browser with MCP tool abilities: BACKLOG, "On the in-built
  browser" (an iframe fails on the sites worth opening). The stdio MCP server
  over the app's own tools is built, `python -m tessellate.mcp_server`.
- A VS Code extension: BACKLOG, "A VS Code extension" (no purpose stated yet).
- The status dot's error state can be reached: checked
  (L-world-class-184, `tests/test_ai_status_error_reachable.py`).
- Streamline and optimise the backend and every AI interaction: closed as a
  measured list of seven (L-world-class-185, HISTORY 2026-11-22); new work goes
  through `tests/test_ai_wire_budget_185.py` and the perf ratchets.
- "I wrote 'ai is cool' as a note and it was filed under sketches": checked
  (`tests/test_filing_ai_is_cool.py`).
- `docs/index.html`'s text against the README: checked (L-world-class-187,
  `tests/test_docs_site_matches_readme.py`).

## From the audits

- **A dry run for the background librarian.** It edits notes unattended and there
  is no way to see what it would do first. `taskhistory` already records each run;
  what is missing is "here is the diff, apply or discard".
- **Sweep for orphans on a schedule, not just vectors.** `clean_orphaned_vectors`
  is the right pattern, and `clean_orphaned_board_cards` follows it; attachments
  want it too.
- **The sketch highlighter is at 5% opacity**, which is roughly twenty passes
  before anything shows. Almost certainly a mistyped value, but it is a taste call,
  so it was left alone rather than changed during an audit.
- **A memory-stream screen.** Built: Settings, What it remembers lists everything
  the AI has saved, says how much of it reaches the model, and lets each one be
  edited, switched off or forgotten.
- **Whiteboard cards should die with their note.** Built: they are swept with the
  orphaned vectors on the background pass.
