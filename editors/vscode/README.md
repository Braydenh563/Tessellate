# Tessellate for VS Code

Save a selection or a typed note to your own Tessellate notebook, search your notes and insert a link or the text, and open a note in a read-only editor. It talks only to the Tessellate server on this computer: no telemetry, no other host.

## Set up

1. Start Tessellate. Set `tessellate.address` in settings if it is not on `http://127.0.0.1:8000`.
2. Run **Tessellate: Sign in** and type your Tessellate password. The session token is kept in VS Code's secret storage, never in settings. Run **Tessellate: Sign out** to forget it.

## Commands

- **Save selection as a note** (also in the editor context menu): the selection, fenced as code, with the file it came from.
- **Save a typed note**: one line from the input box.
- **Search notes and insert a link**: inserts `[[title]]` at the cursor.
- **Search notes and insert the text**: inserts the note's text.
- **Open a note (read only)**: opens `tessellate:/<id>.md` in a read-only editor.

## Install without a build step

Copy this folder to your extensions folder, or run `npx @vscode/vsce package` and install the `.vsix`. There is no build step: `extension.js` and `lib/client.js` run as written.

## Tests

`node --test test/client.test.js` runs the API client against a fake server. `tests/test_vscode_extension.py` in the app checks that every route the client calls exists in Tessellate, so a renamed route fails CI. The extension itself has not been run inside VS Code in this repository's environment.

Licence: AGPL-3.0.
