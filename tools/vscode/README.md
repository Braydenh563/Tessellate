# Tessellate for VS Code

Three commands over the app's own tool server (`POST /mcp`, see `docs/MCP.md`). It adds no new route and no new kind of token.

- **Tessellate: Search notes** shows the matches in a quick pick; choosing one opens it in the app (`#/notes/<id>`).
- **Tessellate: Save selection as a note** saves the selected text as a new note. It is also on the editor's right-click menu. It needs a token made with "Can add and change notes".
- **Tessellate: Set tool server token** keeps a token from Settings, Tools it can use, in VS Code's secret storage. With a token set, VS Code's chat also gets the notebook's tools ("Tessellate notes" in its MCP server list).

The app must be running on this computer. `tessellate.url` sets where it listens (default `http://127.0.0.1:8000`).

## Install from the checkout

Needs VS Code 1.101 or later. Run `npx @vscode/vsce package` in this folder, then Extensions, Install from VSIX. It is not on the Marketplace yet.

## Tests

`tests/test_vscode_extension.py` runs `test/harness.js` under node. It replays the request the extension builds against the real `/mcp` route with a real token, and it activates the extension against a stub `vscode` module.
