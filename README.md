<div align="center">

<img src="frontend/icon-512.png" alt="Tessellate" width="120">

# Tessellate <sub><sup>notes</sup></sub>

<i>Your notes, pieced together</i><br>
<sub>Formerly MemoryMap AI</sub>

**Capture anything. Ask anything. Tessellate files it, links it and answers from it, all on your own device.**

[Download](https://github.com/Braydenh563/Tessellate/releases/latest) ·
[Quick start](#quick-start) ·
[Website](https://braydenh563.github.io/Tessellate/) ·
[Documentation](#documentation)

[![CI](https://github.com/Braydenh563/Tessellate/actions/workflows/ci.yml/badge.svg)](https://github.com/Braydenh563/Tessellate/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Braydenh563/Tessellate/actions/workflows/codeql.yml/badge.svg)](https://github.com/Braydenh563/Tessellate/actions/workflows/codeql.yml)
[![Latest release](https://img.shields.io/github/v/release/Braydenh563/Tessellate)](https://github.com/Braydenh563/Tessellate/releases/latest)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)

[![Last commit](https://img.shields.io/github/last-commit/Braydenh563/Tessellate)](https://github.com/Braydenh563/Tessellate/commits/main)
[![Tests](https://img.shields.io/badge/tests-10%2C200%2B%20offline-brightgreen)](tests)
[![Complexity](https://github.com/Braydenh563/Tessellate/actions/workflows/complexity.yml/badge.svg)](https://github.com/Braydenh563/Tessellate/actions/workflows/complexity.yml)
[![Performance](https://github.com/Braydenh563/Tessellate/actions/workflows/performance.yml/badge.svg)](https://github.com/Braydenh563/Tessellate/actions/workflows/performance.yml)

<img src="docs/screenshots/notes.png" alt="Notes: the categories down the left with their counts, note cards newest first, each with its category, tags and the notes it links to, and the Connections panel for the open note on the right" width="850">

</div>

---

> [!NOTE]
> **Tessellate is in beta.** It works and it is tested, but some parts are
> still rough: you may meet lag in places (long note lists, the graph and mind
> maps), screens that need more polish, and features that are planned but not
> built yet. Your notes stay on your machine and are kept safe by backups, but
> please keep your own copy of anything important while we are in beta. We are
> working through the rough edges release by release, so updates come often.
> If something is slow, broken or missing, [open an issue](https://github.com/Braydenh563/Tessellate/issues)
> and say what you were doing: it is the fastest way to get it fixed.

<details>
<summary><b>Installed it before it was called Tessellate? Open this first.</b></summary>

<br>

The app was renamed, and the installer, the program folder and the downloads
are renamed with it, so the new installer does not update the old one in
place.

1. **Save your notes first.** Copy your data folder somewhere safe:
   `%APPDATA%\MemoryMap AI` (older installs) or `%APPDATA%\Tessellate`.
   Press `Win + R`, paste the path and press Enter. A backup from Settings
   also works.
2. Uninstall the old version. If a folder is left behind, delete it:
   `C:\Program Files\MemoryMap AI` (the program only, not your notes).
3. Download the latest installer from the
   [releases page](https://github.com/Braydenh563/Tessellate/releases/latest)
   and install it.

Your notes live in the data folder, not in Program Files, so the new version
finds them. If it does not, close it and copy your saved folder back to
`%APPDATA%\Tessellate`.

</details>

## What it is

Type a thought and a local AI files it, tags it and links it to what you
already wrote. Ask a question later and get an answer with the notes behind
it.

```
capture a thought  ->  it files itself  ->  ask a question  ->  an answer, with its sources
```

- **Files itself.** Every note lands in a category with tags and links, and
  says how sure it is.
- **Answers you can check.** Each sentence of an answer cites the note it came
  from.
- **Private by design.** One SQLite file on your computer: no account, no
  cloud, no telemetry. The AI runs on your machine. A local model is
  recommended but optional: [Ollama](https://ollama.com), LM Studio or
  llama.cpp's `llama-server` all work.
- **Works without AI.** With no model, Atlas still answers from your notes
  (dates, tasks, reminders, how-to questions) with citations, and the app
  files, searches and keeps every feature working.
- **Quick unlock.** A PIN unlocks the notebook on this computer, kept in the
  system's protected store; the password still works everywhere.
- **More than notes.** Documents, whiteboards and mind maps, a graph of your
  ideas, a timeline and reminders, in one app.

## Features

Open a section for the detail.

<details>
<summary><b>Capture</b>: type, paste, draw, dictate or record; import from Notion, Obsidian, Evernote, Apple Notes and files</summary>

- Type, paste, draw, or dictate and record meetings (transcribed on this machine
  with Whisper). `Alt`+`N` opens a quick note over any tab. `#word` tags a note,
  and Markdown works inline, including `[[wiki links]]` and `==highlights==`.
  Copy or cut with nothing selected takes the whole line, in the capture box
  and in the editors.
- Put an emoji or an icon in a note or a document from one picker (Emoji or
  icon in the toolbar, the Insert menu and the `/` menu): an emoji as itself,
  one of 1,530 icons as `:ph-name:`.
- Bring notes in from a folder of Markdown files, a PDF, Word file or slide
  deck, Notion, Obsidian, Evernote, Apple Notes or a Tessellate notebook folder,
  or clip a web page with a bookmarklet. Importing the same thing twice adds
  only what is new.
- Attach any file. Images are captioned, read by a vision model and run
  through Tesseract OCR (or RapidOCR) where each is available; scanned PDFs are read page
  by page, and the OCR workspace lets you correct each region before it
  becomes a note.
- A note saved while the server is away waits on this device and is sent once
  when the server is back.

</details>

<details>
<summary><b>Organise</b>: filed by meaning, honest certainty, tags, categories, spaces, a background librarian</summary>

- The AI picks a category by meaning (or asks, in guided mode), shows an honest
  estimate of how sure it was (never 100%) and suggests tags, one press to keep each. With no AI, tags come from
  the notes most like it.
- Manage categories and tags by hand: create, rename, merge, split, delete and
  move, each step undoable. Spaces keep separate areas of life apart.
- A background librarian can tag, link and flag duplicates on a schedule you
  set. It never deletes anything.
- Everything lives in the Library: notes, documents, chats, boards and maps,
  images and files, bookmarks, the AI skills, a contents tree and an activity
  log.

</details>

<details>
<summary><b>Ask</b>: answers with a citation per sentence, saved chats, Agent mode with tools and skills</summary>

- A question returns a conversational answer and the notes behind it, with a
  numbered citation after each sentence. Chat is saved and resumable, and the
  line under an answer in progress says what is happening: reaching the
  model, reading your notes, thinking, writing, or the tool in use.
- Questions collects the questions your notes ask in passing, and marks one
  answered when a later note answers it.
- In Agent mode the assistant has 72 tools to search, link, organise and act on
  your notebook. Anything destructive asks first, as does any change or web
  request after it has read a web page or an imported note. Every step is
  shown.
- 21 built-in skills (and your own) run multi-step jobs as a visible
  checklist. Small models are first-class: a small-model mode gives a 4B model
  one step and one tool at a time.
- A command palette (`Ctrl`/`Cmd`+`K`) runs any command or goes to any place
  (typed words it cannot match go to Find anything, `Ctrl`+`P`, which
  searches notes and documents), and a popup agent (`Ctrl`+`Shift`+`A`) does things from any tab. Reminders
  take plain language: "call Sam tomorrow evening". The palette also starts a
  timer ("timer 10 minutes") or a stopwatch on the status bar, counts the
  words in a selection, and inserts a template where the cursor is.
- Statistics counts the notebook, your reminders and what you use, with this
  week against last, from the Dashboard's activity heatmap.

</details>

<details>
<summary><b>Write</b>: a long-form editor with live preview, local spelling and grammar, history and export</summary>

- Documents is a long-form editor with Live, Source, Split and Read views,
  spelling and grammar checks that run on your computer, version history,
  focus mode, and code files with line numbers, the line you are on lightly
  highlighted. A document reopens where you left it.
- The Writing room turns rough thoughts into a proper note, or a pasted block
  into several linked notes, before anything is saved.
- Export a document as Markdown, HTML, PDF or Word, and your notes as JSON,
  CSV or Markdown.

</details>

<details>
<summary><b>Visualise</b>: graph, timeline, whiteboards and mind maps, dashboard</summary>

- The Graph draws your notes as a map coloured by category, with the reason
  for each link written down.
- The Timeline puts every note and reminder on a time axis.
- Boards hold cards, sketches, images and shapes that contain text, joined by
  connectors that carry a label, with a library of shapes, flowchart symbols
  and 1,530 icons. Insert, Emoji and icons places an emoji as a sticker or an
  icon you can recolour, and dragging a card, shape or topic to the "Drop here to
  delete" strip at the foot of the canvas deletes it, with an Undo.
- A board can be a mind map, with tasks to tick, a note behind any topic and
  numbered branches. The centre, main branches and deeper topics each get their
  own size and look (Classic, Outline, Boxed or Flat, or your own per level),
  and a topic can wear any icon or emoji. Maps export as Markdown, OPML or
  FreeMind, and import XMind.
- The Dashboard shows your capture streak, statistics, a weekly digest and the
  widgets you choose.

</details>

<details>
<summary><b>Also</b>: themes, accessibility, a guided tour, sign-in</summary>

- Thirteen themes, each in light or dark, with your own accent, type, density
  and corners. A drawn face for every person and persona, and an optional
  corner companion.
- An Interface animations switch (Settings, Appearance, Effects & accessibility)
  turns the short fades and slides off or on, apart from Reduce motion, which
  stills the large movement. A Back and Forward list in the status bar shows
  where you have been, with an icon for each kind.
- Keyboard and screen reader support: named controls, 4.5:1 contrast, a layout
  that holds at 400% zoom, and a switch for single-key shortcuts.
- A guided tour, and errors written as plain sentences that say what to do.
- Signing in is on by default and can be turned off on a computer only you use.

</details>

## Screenshots

Captured from the app in the dark theme at 1440 by 900.

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="The dashboard in the dark theme: a greeting with the note count, reminders and capture streak, a search box, quick actions, and widgets for reminders, recently added notes, favourites, quick capture, boards and recent documents" width="850">
</p>

<p align="center">
  <img src="docs/screenshots/ask.png" alt="Notes, Ask: the question What do I still need to book for Portugal, an answer naming the train tickets and the hire car with a numbered citation after each sentence, and the matching notes beside it" width="850">
  <br><sub><b>Ask</b>: a question to your own notes, answered with a numbered citation to the note behind each sentence</sub>
</p>

<p align="center">
  <img src="docs/screenshots/chat.png" alt="Chat: a saved conversation about a product launch, the answer as a numbered list with citations, the notes it was grounded in, suggested next questions, and the composer with skills, web search, plan and agent mode" width="850">
  <br><sub><b>Chat</b>: ask in plain English, with skills, web search, a plan step and agent mode beside the box</sub>
</p>

<p align="center">
  <img src="docs/screenshots/graph.png" alt="Graph: seventy-five notes as a map coloured by category, with a dense cluster of work notes, a dense cluster of trip notes, a looser web of reading and recipes, a training plan with its branches, and loose notes on their own" width="850">
  <br><sub><b>Graph</b>: dense clusters, loose webs and notes on their own, coloured by category; a link with a reason is drawn in the accent</sub>
</p>

<details>
<summary><b>Seventeen more</b>: the Library and its Activity view, Timeline, Reminders, Documents and focus mode, a board, a mind map, the command palette, Tools and features, Settings, Your look, the popup agent, the corner companion, Atlas, light and dark side by side, and a phone</summary>
<br>

<p align="center">
  <img src="docs/screenshots/library.png" alt="Library: chats, boards, mind maps, documents and notes as cards in one grid, with a filter chip per kind and its count" width="850">
  <br><sub><b>Library</b>: everything you have made, in one place</sub>
</p>

<p align="center">
  <img src="docs/screenshots/activity.png" alt="Library, Activity: one line per thing you did, newest first: when, what was done, and the detail" width="850">
  <br><sub><b>Activity</b>: a record of what you did, one line each, beside what you made</sub>
</p>

<p align="center">
  <img src="docs/screenshots/timeline.png" alt="Timeline: notes and reminders in a feed with a header per day, each row with its category, tags and time, and a density strip down the right" width="850">
  <br><sub><b>Timeline</b>: every note and reminder on a time axis</sub>
</p>

<p align="center">
  <img src="docs/screenshots/reminders.png" alt="Reminders: a magic add box, a form with date, time, priority and repeat, quick set steppers, and the list of open reminders, each linked to the note it came from" width="850">
  <br><sub><b>Reminders</b>: due dates with priority and repeats, linked to the note they came from</sub>
</p>

<p align="center">
  <img src="docs/screenshots/documents.png" alt="Documents: a launch brief open in the editor, with headings, a bulleted list and a table, the recent documents beside it and the word count below" width="850">
  <br><sub><b>Documents</b>: a long-form editor with Live, Source, Split and Read views; it reopens where you left off</sub>
</p>

<p align="center">
  <img src="docs/screenshots/focus.png" alt="Documents in focus mode: the page alone under a slim bar, with the writing suggestions panel open beside it" width="850">
  <br><sub><b>Focus mode</b>: the page and nothing else, with the writing checks beside it when you want them</sub>
</p>

<p align="center">
  <img src="docs/screenshots/whiteboard.png" alt="A board: a banner, coloured cards in two columns, and a release flow of shapes with text inside them, joined by connectors labelled yes, no and after a week" width="850">
  <br><sub><b>Boards</b>: cards, shapes that hold text, and connectors that carry a label</sub>
</p>

<p align="center">
  <img src="docs/screenshots/map.png" alt="A mind map of a trip, laid out both ways from the root: numbered branches in a boxed look with a size and weight per level, icons on the main topics, topics that are tasks with ticks and a done count on their parent, and a mark on the topics that hold a note" width="850">
  <br><sub><b>Mind maps</b>: numbered branches, a look per level, icons, topics that are tasks, and a note behind any topic</sub>
</p>

<p align="center">
  <img src="docs/screenshots/palette.png" alt="The command palette: the word new matching the create commands, a preview of the chosen one, and a last row that searches everything" width="850">
  <br><sub><b>Command palette</b>: Ctrl/⌘-K runs a command or goes to a place, and hands a search to Find anything</sub>
</p>

<p align="center">
  <img src="docs/screenshots/features.png" alt="The Tools and features browser: a search box over grouped rows, each naming one thing the app can do" width="850">
  <br><sub><b>Tools &amp; features</b>: everything the app can do, grouped and searchable</sub>
</p>

<p align="center">
  <img src="docs/screenshots/settings.png" alt="Settings, Appearance: thirteen themes as swatches, with saved looks below and the section list on the left" width="850">
  <br><sub><b>Settings</b>: thirteen themes, your own accent, type, density and corners, and every setting searchable</sub>
</p>

<p align="center">
  <img src="docs/screenshots/your-look.png" alt="Settings, Profile, Your look: the face drawn from the name Maya, Shuffle, and a picker for each part: look, mood, hair, hair colour, skin, clothes, headwear, eyewear and what you hold" width="850">
  <br><sub><b>Your look</b>: a face drawn from your name, and every part of it yours to choose</sub>
</p>

<p align="center">
  <img src="docs/screenshots/agent.png" alt="The popup agent over the Notes tab: Atlas beside the title, the box to ask it to do something, and starters grouped by Capture, Find, Summarise and Remind" width="850">
  <br><sub><b>Popup agent</b>: ask Atlas to do something from any tab</sub>
</p>

<p align="center">
  <img src="docs/screenshots/companion.png" alt="Chat with Atlas as the corner companion, settled beside a saved conversation" width="850">
  <br><sub><b>The corner companion</b>: Atlas, you, a persona or a character of your own, keeping you company on any page</sub>
</p>

<p align="center">
  <img src="docs/screenshots/atlas.png" alt="Atlas, delighted: a small astral figure on a night-sky tile, eyes closed in a wide smile with rosy cheeks and two sparkles, a ring of orbiting stars round its head and a nebula stream curling round its body" width="260">
  <br><sub><b>Atlas</b>: the star spirit who keeps your notebook</sub>
</p>

<p align="center">
  <img src="docs/screenshots/theme-split.png" alt="The dashboard, the left half in the light theme and the right half in the dark theme, split down the middle" width="850">
  <br><sub><b>Light or dark</b>: every theme comes in both, or follows your system</sub>
</p>

<p align="center">
  <img src="docs/screenshots/phone.png" alt="The Notes tab at phone width in the dark theme: one column of note cards, a New note button and the tab bar along the bottom" width="390">
  <br><sub><b>On a phone</b>: one column, the tabs at your thumb</sub>
</p>

</details>

## Quick start

Pick the way that suits you. Only the last needs a terminal.

**Windows.** Download `Tessellate-Setup-*.exe` from the
[latest release](https://github.com/Braydenh563/Tessellate/releases/latest)
and run it. The app opens in its own window. Windows shows a "protected your
PC" screen because the installer is not code-signed yet:
[what to click](docs/INSTALL.md#windows-installer).

**Linux.** Download `Tessellate-*-linux-x86_64.tar.gz` from the same page,
unpack it with `tar -xzf` and run `Tessellate`. Use the tarball rather than
the `.zip` beside it: a zip may drop the executable bit and leave a launcher
that will not start. The window needs GTK and WebKit (`python3-gi` and
`gir1.2-webkit2-4.1` on Debian and Ubuntu).

**macOS, or any platform from source.** Clone the repository and run
`./start-desktop.sh` for the app's own window, or `./start.sh` for a browser
tab (on Windows, `start-desktop.bat` or `start.bat`). The launcher builds a
private Python environment, installs everything and opens
<http://localhost:8000>. Add `--doctor` to check the machine and print a fix
for each problem. Each action is also one double-click: `doctor`, `reinstall`
(rebuilds the Python environment; your notes are untouched) and `tools` (a
menu of every launcher action), as `.sh` and `.bat`. The same actions are in the app, under Settings, About, Maintenance. [docs/INSTALL.md](docs/INSTALL.md) has a step-by-step
version for first-time terminal users.

**Then:**

1. Choose a password when the app first opens.
2. Add the AI. Install [Ollama](https://ollama.com) and pull a model that fits
   your machine; `ollama pull llama3.2` through your computer's terminal is a safe start. Which model, from
   "runs on a laptop with no GPU" upwards, is in [docs/MODELS.md](docs/MODELS.md).
   LM Studio, llama.cpp's `llama-server`, Jan and vLLM work too, through
   Settings, Models.
3. Write a note, then ask about it in Notes, Ask.

**A first install needs the internet once.** The first setup downloads the search model and the packages you chose; after that Tessellate works offline.

**The first launch downloads the search model.** Search and filing by meaning
use a built-in model that needs the `sentence-transformers` package. If it is
missing, the app installs it the first time it is needed: a one-time download
of several hundred MB (more on Windows, where it brings torch) that needs the
internet and can take several minutes. Settings, Search and index, Search
engine says when it is running. To avoid the download, pull `nomic-embed-text`
in Ollama and pick it in the same place.

## Requirements and optional extras

- **To run it:** the Windows installer and the Linux tarball need nothing else.
  From source you need Python 3.11 or newer (CI runs 3.11 to 3.13).
- **For the AI:** [Ollama](https://ollama.com) or any OpenAI-compatible server.
  The app is useful without one.
- **Optional extras.** Settings, Packages installs each one from inside the
  app, with no terminal. None is needed for the core.

| Extra | What it adds |
| --- | --- |
| Search by meaning (sentence-transformers) | Matching ideas rather than words; about 2 GB with torch |
| Voice notes (faster-whisper) | Local dictation for the microphone buttons |
| Desktop window (pywebview) | The app in its own window, and a tray icon on Windows |
| Import documents (markitdown) | PDF, Word and slide decks become notes |
| Read scanned PDFs (pypdfium2) | Scanned pages become images a vision or OCR model can read |
| Search inside images (Tesseract OCR) | Text in images becomes searchable; also needs the Tesseract program |
| Read images without Tesseract (RapidOCR) | A second local reader, nothing else to install; used when Tesseract isn't ready |
| Run Python files (Pyodide) | Runs a `.py` document in a sandbox; a pinned download that works offline |
| Tool calling without Ollama (needle) | A small built-in model that picks tools when no model server is running; a pinned download that works offline |
| Translate offline (Bergamot, English to Spanish) | Translate this, in the command palette, with no model; a pinned 27 MB download that works offline |

## Privacy

Everything lives in one folder: `tessellate.db` (your notes), `preferences.json`,
`uploads/` and `backups/` (a snapshot once a day). Set `TESSELLATE_DATA_DIR` to
put it elsewhere. Settings, Import & export exports your notes as JSON, CSV or
Markdown, the whole notebook as a folder (each note as Markdown with its
attachments and a `.json` file of every field, plus documents and boards,
which imports back whole), or as a full backup that you can seal with a
password. Every import keeps a report naming anything it left out.

- The server listens on this computer only. Letting a phone or another computer
  on your network in is a switch in Settings, Account & security; it always
  asks for your password, over HTTPS with a certificate made on this computer
  (Settings, Account & security shows its fingerprint).
- The AI runs where you point it, and a setting that is on by default
  refuses a model address that is not on your computer or network.
- Private notes are encrypted at rest with a key derived from your password,
  and kept out of search, the graph and every AI tool. A recovery key, shown
  once, lets "Forgot your password?" on the lock screen set a new password
  and keep them.
- Web search is off by default, and the update check waits for your answer to
  the question the first start asks. Web search sends only your search words.
- Settings, Privacy lists every connection the app has made.

[docs/PRIVACY.md](docs/PRIVACY.md) has the full model, including sessions, the
browser protections and what to do if you forget your password. To report a
vulnerability, see [SECURITY.md](SECURITY.md).

## Performance

Each interaction has a time budget, held by a test that fails when it is
exceeded (`tests/test_budgets.py` for the server, `tests-e2e/specs/budgets.spec.js`
in a real browser; the table is `BUDGETS` in `src/tessellate/api/routes_bench.py`).
Measured in headless Chromium on a four-core machine under load, on a 500-note
notebook with a board of 500 objects and a document of 50,000 words. Each
measured figure is the slowest of four runs' medians; the budget is 1.5 times it.

| Interaction | Measured (ms) | Budget (ms) |
| --- | --- | --- |
| Boot to first paint | 713 | 1070 |
| First interaction | 4639 | 6960 |
| List paint | 139 | 210 |
| Search | 30 | 50 |
| Board open | 108 | 170 |
| Document open | 359 | 540 |

The same figures as bars, slowest first (first interaction left out, as it would
dwarf the rest):

| Interaction | Measured | |
| --- | --- | --- |
| Boot to first paint | 713 ms | ██████████████ |
| Document open | 359 ms | ███████ |
| List paint | 139 ms | ███ |
| Board open | 108 ms | ██ |
| Search | 30 ms | █ |

The first interaction is the first click the app answers after a cold start,
with the session kept. `GET /models/bench/budgets?live=true` times the server's
share of each against your own notebook.

## Documentation

| Document | What it answers |
| --- | --- |
| [INSTALL](docs/INSTALL.md) | The Windows installer, the launcher, manual setup, updating and uninstalling |
| [DOCKER](docs/DOCKER.md) | Running Tessellate in Docker: compose, volumes, ports, a model server on the host |
| [MCP](docs/MCP.md) | The MCP server: tools, resources, client config, security |
| [MODELS](docs/MODELS.md) | Which model suits your machine, and using a server other than Ollama |
| [PRIVACY](docs/PRIVACY.md) | What touches the network, private-note encryption, sessions |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | Common problems and their fixes |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | How the pieces fit, and where to change any given thing |
| [DESIGN](docs/DESIGN.md) | The design system every screen is written against |
| [RELEASING](docs/RELEASING.md) | How a version is cut and published |
| [ROADMAP](docs/ROADMAP.md) | What is open, and in what order |
| [CHANGELOG](CHANGELOG.md) | What changed, release by release |
| [SECURITY](SECURITY.md) | How to report a vulnerability |

**Status.** Version 0.5.0. This is a beta (`0.x`). Capture, chat with
checkable answers, the graph, documents, boards and mind maps, the OCR
workspace, private notes and themes are built and stable, with desktop builds
for Windows and Linux. Settings, Help has a guided tour of the real controls.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first: the
one rule is that every feature must work with no cloud service. In short:

```
pytest -n auto                  # 11,200+ tests, fully offline, every AI call faked
bash scripts/gate.sh --changed  # lints, node --check, ruff, and the tests that name your files
ruff check .                    # what CI lints with
```

The frontend is plain HTML, CSS and JavaScript in `frontend/`, served as it is,
with no build step. Run `node --check` on each script you edit.
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) maps the backend modules and the
frontend's load order.

## Licence

[GNU Affero General Public License v3.0](LICENSE).

You may use, study, modify and share this, and anything built on it must stay
under the same licence, including a modified copy run as a network service.
Tessellate is a local-first app, and the AGPL keeps a closed, hosted version of
it from being offered back to the people it was written for.

The libraries vendored into the app, with their versions and licences, are
credited in [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).
