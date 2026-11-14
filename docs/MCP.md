# Use Tessellate from an MCP client

Tessellate includes a local MCP (Model Context Protocol) server, so a client such as Claude Desktop or Claude Code can search and work with your notes. Tessellate is designed to pair with a local AI model (Ollama, LM Studio or llama.cpp recommended) but works without one; the MCP server does not use Tessellate's own model at all, because the client brings its own.

The code is `src/tessellate/mcp_server.py`.

## What it exposes

Three things, all over standard input and output:

- **Tools:** the app's own tool registry, minus any tool that is destructive (the `delete_*` tools and `merge_categories`), interactive (`ask_user`, `make_plan`, `run_skill`, `compress_chat`), or chat-only (`get_app_navigation`, `search_chat_history`). A tool you switched off in Settings, Tools is hidden too, and `web_search` and `read_url` appear only if you enabled them.
- **Resources:** each note as `memorymap://note/<id>` (markdown). Private notes are never served.
- **Prompts:** your saved skills, filled in the way a skill run fills them. A prompt is text for the client's model; it runs nothing.

With default settings the server offers **28 tools**, all of them reads (of 73 in the registry). The write tools in the table below are offered only once you tick **Let that app add and change notes** (Settings, Tools it can use, Use these tools from another app; off by default), which makes it 55. Each tool carries `readOnlyHint`, so a client can auto-approve the reads.

### Tool list

| Tool | Kind | What it does |
| --- | --- | --- |
| `calculate` | read | Work out a sum, percentage, unit or currency conversion, or count of days, the way the app does. |
| `check_answer` | read | Check a draft answer against the text it came from: lists any number or name in the answer the sources do not contain. |
| `count_notes` | read | Count the user's notes: in total, per category, or for one category, tag, age or untagged. |
| `find_contradictions` | read | Finds places where the user's own notes disagree with each other, a decision reversed, a date that moved, a view they changed. |
| `find_similar_notes` | read | Traverse the knowledge graph semantically to find notes that read similarly to a given note. |
| `get_current_time` | read | The date and time now, here or in a named place; for time-aware answers and reminder times. |
| `get_document` | read | Read one document in full, by id. |
| `get_note` | read | Read one note in full, by id. |
| `list_categories` | read | List every category with how many notes it holds. |
| `list_documents` | read | List the user's long-form documents, newest first, optionally filtered by a word in the title or body. |
| `list_library` | read | Find shapes, flowchart symbols, arrows, frames (Kanban, SWOT, retrospective), icons and the person's own saved items in the board's object library, by a word. |
| `list_notes` | read | Walk through the user's notes, newest first, optionally by category, tag, age or untagged. |
| `list_reminders` | read | List the user's reminders, soonest first. |
| `list_skills` | read | List the user's saved skills: repeatable jobs you can start with run_skill. |
| `list_tags` | read | List every tag in use with how many notes carry it, most-used first. |
| `notebook_overview` | read | Categories, tags and the total note count, in one call: use it instead of list_categories + list_tags + count_notes for the notebook's overall shape. |
| `notebook_structure` | read | See the SHAPE of the notebook rather than its filing: which notes are clustered together, which are the best-connected hubs, and which are connected to nothing at all. |
| `path_between` | read | Answer 'how are these two notes related?': the chain of connections joining them, each step a link somebody made, a reply thread, or a shared tag. |
| `read_file` | read | Read everything the app knows about one file: its caption and the text read out of it. |
| `read_mindmap` | read | Read a mindmap as an indented outline: its title, then every node with its id, kind and any note or document it stands for. |
| `read_text` | read | Read the dates, times, durations, amounts and units in a piece of text exactly as the app reads them, each with how it was read. |
| `read_whiteboard` | read | Read a whiteboard board's contents: which notes are placed as cards, any text boxes, how many images, and which cards are linked to which. |
| `related_notes` | read | Walk the connections around a note: what it links to, what replies to it, and what shares its tags, each with HOW it connects and how far away. |
| `search_files` | read | Search the files the user has uploaded (photos, scans, PDFs, attachments) by name, caption or the text read out of them. |
| `search_help` | read | How a Tessellate feature or setting works, from its guide. |
| `search_notes` | read | Search the user's notes by meaning or keywords. |
| `search_whiteboard` | read | Search across every whiteboard board for a card or text box containing a word: use this for 'which board did I put X on?' when you don't already know the board. |
| `summarize_notes` | read | Gather the user's recent notes (optionally from the last N days or a category) so you can summarise them. |
| `add_board_shape` | write | Draw a rectangle, ellipse or diamond with words in it, or a frame (a titled region), on a board at x, y with a width and height. |
| `add_map_node` | write | Add ONE node to a mindmap, under a parent or as a new root. |
| `add_whiteboard_card` | write | Place an existing note as a card on a whiteboard board. |
| `add_whiteboard_link` | write | Draw a link between two cards already on a whiteboard board (add_whiteboard_card first). |
| `audit_link_reasons` | write | Audits vague graph link reasons (like 'similar in meaning') and rewrites them by deducing a specific reason based on both notes. |
| `check_learned` | write | Check what the app learned about the user: re-read every claim and question it worked out against its note as written now, retire what no longer holds (note edited or deleted, a joke, quote or draft, marked wrong, repeated) and flag what needs a look (two notes disagree, a date that has passed). The retired ones can be undone in Settings, What it learned. |
| `complete_reminder` | write | Mark a reminder done (or not done). |
| `create_category` | write | Make a new category. |
| `create_document` | write | Write a new long-form document (an essay, a report, a write-up) and save it. |
| `create_mindmap` | write | Create an empty mindmap with one root topic on it, for 'start a mind map about X'. |
| `create_note` | write | Save a new note for the user. |
| `edit_note` | write | Change a note's text, category, or replace its whole tag list. |
| `generate_diagram` | write | Place a whole tree of notes on a whiteboard board in one call. |
| `link_map_nodes` | write | Draw a cross-link between two existing nodes on one mindmap, what a tree can't express ('this depends on that'); read_mindmap gives their ids. |
| `link_notes` | write | Connect a note to one or more related notes. |
| `map_from_note` | write | Make a mind map from one note in one call, for 'turn this note into a map': its title is the centre, its headings and lists the branches. |
| `pin_note` | write | Add a note to Favourites (or remove it). |
| `place_library_item` | write | Place a library item (a ref from list_library) on a board, centred at x, y. |
| `rename_category` | write | Rename a category; merges if the new name is already taken. |
| `rename_tag` | write | Rename a tag everywhere it's used (merges if the new name exists). |
| `restore_board_item` | write | Put back a board item delete_board_item took off: pass the item text its undo gave. |
| `restore_note` | write | Bring a note back from the recycle bin. |
| `save_skill` | write | Create a saved skill, or update one by using the same name. |
| `save_user_preference` | write | Suggest a standing preference for the user to accept. |
| `set_reminder` | write | Create a reminder; put when in the user's own words. |
| `tag_note` | write | Add and/or remove individual tags on one or multiple notes. |
| `unlink_notes` | write | Remove a connection between two notes that shouldn't be linked. |

The list follows the registry, so it grows as the app does: `tools/list` from your own install is the exact answer, and Settings, Tools it can use shows what is on.

## Start it

You do not normally start it by hand: the client launches it. It speaks stdio, one JSON-RPC message per line, and uses the same notebook as the app (set `TESSELLATE_DATA_DIR` to the same folder).

| Install | Command |
| --- | --- |
| Source checkout | `python -m tessellate.mcp_server` (with `PYTHONPATH=src` from the repo root, or the venv that has the app's packages) |
| Packaged app | `Tessellate --mcp` |

The app need not be running. Settings, Tools it can use shows the exact config for your install, with this interpreter, your data folder and this notebook's token filled in. Copy that rather than the examples below if they differ.

**The token.** The server answers only a client that passes this notebook's token as `TESSELLATE_MCP_TOKEN` (only `ping` works without it). The token is made the first time Settings shows the snippet and is kept as a secret setting (the operating system's protected store, or an owner-only file under `secrets/` in the data folder). A client without it, or with a wrong one, is told to copy the snippet from Settings, Tools it can use.

## Client configuration

All three take the same `command`, `args` and `env` shape. Source checkout, with your own paths:

```json
{
  "mcpServers": {
    "tessellate": {
      "command": "/path/to/MemoryMap-AI/.venv/bin/python",
      "args": ["-m", "tessellate.mcp_server"],
      "env": {
        "TESSELLATE_DATA_DIR": "/path/to/your/data",
        "TESSELLATE_MCP_TOKEN": "the token from the Settings snippet",
        "PYTHONPATH": "/path/to/MemoryMap-AI/src"
      }
    }
  }
}
```

`PYTHONPATH` is needed only when the app is not installed into that Python. The in-app snippet uses the interpreter that is running the app and sets `TESSELLATE_DATA_DIR` and `TESSELLATE_MCP_TOKEN`.

Packaged app (the in-app snippet fills in the real executable path):

```json
{
  "mcpServers": {
    "tessellate": {
      "command": "/path/to/Tessellate",
      "args": ["--mcp"],
      "env": {
        "TESSELLATE_DATA_DIR": "/path/to/your/data",
        "TESSELLATE_MCP_TOKEN": "the token from the Settings snippet"
      }
    }
  }
}
```

- **Claude Desktop:** Settings, Developer, Edit config opens `claude_desktop_config.json`; merge the `mcpServers` entry in and restart Claude Desktop.
- **Claude Code:** `claude mcp add tessellate -e TESSELLATE_DATA_DIR=/path/to/your/data -e TESSELLATE_MCP_TOKEN=<token> -- /path/to/python -m tessellate.mcp_server`, or put the same entry in a project `.mcp.json`.
- **VS Code:** no extension is needed: VS Code runs MCP servers itself. Put the same command, arguments and environment in `.vscode/mcp.json` under `"servers": {"tessellate": {"type": "stdio", "command": ..., "args": [...], "env": {...}}}`, or run MCP: Add Server from the Command Palette, then pick the Tessellate tools in Copilot Chat's agent mode.
- **Other clients:** any client that can launch a stdio server takes the same command, arguments and environment. The server speaks MCP protocol versions 2025-06-18, 2025-03-26 and 2024-11-05.

## Security model

- **Local only.** There is no network listener and no port. The client starts the process, and the process talks over the pipe the client holds. Nothing else can connect.
- **A token, not the password.** The server refuses every request (except `ping`) from a process that does not pass this notebook's token as `TESSELLATE_MCP_TOKEN`, so being able to start a program as you is no longer enough to read notes through it. The server does not ask for the app password. The trust boundary is still your operating system account, since anyone who can run a process as you can open the notebook's database file, so do not add the snippet to a client you do not trust.
- **Not through Docker or the LAN.** The server is not part of the web app, so LAN mode and a container's published port do not expose it. A client in another place cannot reach it unless you run the command there (for example over SSH, which is your own choice).
- **What a client can do:** read and search notes, documents, files, boards and reminders. Only after you tick **Let that app add and change notes** can it make the non-destructive writes in the table above (create and edit notes, tags, links, reminders, boards, skills); with it off a client cannot change anything, even if a note's text tells its model to. Writes are recorded in Library, Activity under the client's own name (for example "Claude Desktop").
- **What it cannot do:** delete anything (no `delete_*` tool, no `merge_categories`), read private notes, run a skill, or reach the internet unless you switched `web_search` or `read_url` on. A tool you disable in Settings, Tools disappears from the client on its next start.
- **Notes are data.** A note's text goes to the client's model. If the client is a hosted service, that is the one place your notes leave the machine, and it is your choice of client, not Tessellate's. See [PRIVACY.md](PRIVACY.md).

## Troubleshooting

- **The client says the server failed to start:** run the same command in a terminal. It should wait silently for input; press Ctrl+C to exit. An import error means the `python` in the config lacks the app's packages: use the app's venv or set `PYTHONPATH`.
- **Notes are missing or it shows an empty notebook:** `TESSELLATE_DATA_DIR` is not the folder the app uses. Settings, Tools it can use shows the right one.
- **`Tessellate --mcp` says it needs standard input and output:** it was run by hand in a window. A client has to launch it.
- **The client says the server needs `TESSELLATE_MCP_TOKEN`, or has no token yet:** copy the snippet again from Settings, Tools it can use (opening it makes the token), and restart the client.
- **A tool you expect is absent:** it is destructive, interactive or chat-only, switched off in Settings, Tools, or a write tool while Let that app add and change notes is off. Restart the client after changing it.
- **Changes in the app do not show up:** the server opens a fresh database session per call, so reloading the client's tool list is enough; restart it if a switch changed.
- **Quick check:** `printf '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n' | TESSELLATE_MCP_TOKEN=<token> python -m tessellate.mcp_server` prints the tool list as one JSON line.

Related: [INSTALL.md](INSTALL.md#running-it) lists the launcher commands, [DOCKER.md](DOCKER.md) the container setup.
