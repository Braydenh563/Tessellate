// Tessellate for VS Code (L-world-class-183, INBOX 1862): three commands over
// the app's own tool server. No new route, no new token kind: the token is one
// made in Settings, Tools it can use, kept in VS Code's secret storage.
"use strict";

const vscode = require("vscode");
const { call, noteItems, noteLink, base, ToolServerError } = require("./client");

const SECRET = "tessellate.token";

function url() {
  return vscode.workspace.getConfiguration("tessellate").get("url");
}

async function guarded(run) {
  try {
    return await run();
  } catch (error) {
    vscode.window.showErrorMessage(error instanceof ToolServerError ? error.message : `Tessellate: ${error.message}`);
    return undefined;
  }
}

function activate(context) {
  const secrets = context.secrets;
  const changed = new vscode.EventEmitter();

  context.subscriptions.push(
    vscode.commands.registerCommand("tessellate.setToken", async () => {
      const token = await vscode.window.showInputBox({
        prompt: "Paste a token from Tessellate's Settings, Tools it can use",
        password: true,
        ignoreFocusOut: true,
      });
      if (token === undefined) return;
      await (token.trim() ? secrets.store(SECRET, token.trim()) : secrets.delete(SECRET));
      changed.fire();
      vscode.window.showInformationMessage(token.trim() ? "Token saved." : "Token removed.");
    }),

    vscode.commands.registerCommand("tessellate.searchNotes", () => guarded(async () => {
      const query = await vscode.window.showInputBox({ prompt: "Search your notes" });
      if (!query || !query.trim()) return;
      const found = await call(url(), await secrets.get(SECRET), "search_notes", { query: query.trim(), limit: 10 });
      const items = noteItems(found);
      if (!items.length) {
        vscode.window.showInformationMessage(`No notes match "${query.trim()}".`);
        return;
      }
      const pick = await vscode.window.showQuickPick(items, { matchOnDescription: true, matchOnDetail: true });
      if (pick) await vscode.env.openExternal(vscode.Uri.parse(noteLink(url(), pick.id)));
    })),

    vscode.commands.registerCommand("tessellate.saveSelection", () => guarded(async () => {
      const editor = vscode.window.activeTextEditor;
      const text = editor ? editor.document.getText(editor.selection) : "";
      if (!text.trim()) {
        vscode.window.showInformationMessage("Select some text to save first.");
        return;
      }
      const made = await call(url(), await secrets.get(SECRET), "create_note", { content: text });
      const open = "Open in Tessellate";
      const choice = await vscode.window.showInformationMessage(made.label || "Saved as a note.", open);
      if (choice === open && made.id) await vscode.env.openExternal(vscode.Uri.parse(noteLink(url(), made.id)));
    })),
  );

  // VS Code's own chat agents get the notebook's tools through the same door,
  // with the same token: reads only unless that token was made to write.
  if (vscode.lm?.registerMcpServerDefinitionProvider && vscode.McpHttpServerDefinition) {
    context.subscriptions.push(
      vscode.lm.registerMcpServerDefinitionProvider("tessellate.notes", {
        onDidChangeMcpServerDefinitions: changed.event,
        provideMcpServerDefinitions: async () => {
          const token = await secrets.get(SECRET);
          if (!token) return [];
          return [new vscode.McpHttpServerDefinition(
            "Tessellate notes",
            vscode.Uri.parse(`${base(url())}/mcp`),
            { Authorization: `Bearer ${token}` },
          )];
        },
      }),
    );
  }
  context.subscriptions.push(
    changed,
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("tessellate.url")) changed.fire();
    }),
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
