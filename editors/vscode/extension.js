"use strict";
// Tessellate for VS Code. Talks to the local Tessellate server only: no
// telemetry, no other host. The address is a setting; the session token is
// kept in VS Code's secret storage after Tessellate: Sign in, or a tool server
// token after Tessellate: Sign in with a token.
const vscode = require("vscode");
const { Client, noteTitle, normaliseBase, TOOL_TOKEN_PREFIX } = require("./lib/client");

const SCHEME = "tessellate";
const TOKEN_KEY = "tessellate.token";

function activate(context) {
  const notes = new Map();
  const changed = new vscode.EventEmitter();
  const toolsChanged = new vscode.EventEmitter();
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(SCHEME, {
      onDidChange: changed.event,
      provideTextDocumentContent: async (uri) => {
        const id = uri.path.replace(/^\/+|\.md$/g, "");
        if (!notes.has(id)) notes.set(id, (await (await client()).getNote(id)).content);
        return notes.get(id);
      },
    }),
  );

  async function client() {
    const address = vscode.workspace.getConfiguration("tessellate").get("address");
    return new Client(address, (await context.secrets.get(TOKEN_KEY)) || "");
  }

  // One wrapper so every command reports a failure the same way.
  function command(name, run) {
    context.subscriptions.push(
      vscode.commands.registerCommand(name, async (...args) => {
        try { await run(...args); } catch (error) { vscode.window.showErrorMessage(error.message); }
      }),
    );
  }

  command("tessellate.signIn", async () => {
    const password = await vscode.window.showInputBox({ prompt: "Tessellate password", password: true, ignoreFocusOut: true });
    if (!password) return;
    const api = await client();
    await context.secrets.store(TOKEN_KEY, await api.signIn(password));
    toolsChanged.fire();
    vscode.window.showInformationMessage("Signed in to Tessellate.");
  });

  //: A tool server token (Settings, Tools it can use) does not idle out, can be
  //: limited to some categories or tags, and is revoked there (L-world-class-627).
  command("tessellate.signInWithToken", async () => {
    const token = await vscode.window.showInputBox({
      prompt: "Tool server token from Tessellate, Settings, Tools it can use", password: true, ignoreFocusOut: true,
    });
    if (!token) return;
    const api = await client();
    await context.secrets.store(TOKEN_KEY, await api.useToken(token));
    toolsChanged.fire();
    vscode.window.showInformationMessage("Signed in to Tessellate with a token.");
  });

  command("tessellate.signOut", async () => {
    await context.secrets.delete(TOKEN_KEY);
    toolsChanged.fire();
    vscode.window.showInformationMessage("Signed out of Tessellate.");
  });

  command("tessellate.captureSelection", async () => {
    const editor = vscode.window.activeTextEditor;
    const picked = editor && !editor.selection.isEmpty ? editor.document.getText(editor.selection) : "";
    if (!picked) { vscode.window.showInformationMessage("Select some text to capture first."); return; }
    const where = editor.document.uri.scheme === "file" ? `\n\nFrom ${vscode.workspace.asRelativePath(editor.document.uri)}` : "";
    const fence = "```" + (editor.document.languageId === "plaintext" ? "" : editor.document.languageId);
    const note = await (await client()).capture(`${fence}\n${picked}\n\`\`\`${where}`);
    vscode.window.showInformationMessage(`Saved as note ${note.id}.`);
  });

  command("tessellate.captureNote", async () => {
    const text = await vscode.window.showInputBox({ prompt: "Note to save in Tessellate", ignoreFocusOut: true });
    if (!text || !text.trim()) return;
    const note = await (await client()).capture(text.trim());
    vscode.window.showInformationMessage(`Saved as note ${note.id}.`);
  });

  async function pick() {
    const query = await vscode.window.showInputBox({ prompt: "Search your Tessellate notes" });
    if (!query) return null;
    const hits = await (await client()).search(query);
    if (!hits.length) { vscode.window.showInformationMessage("No notes match."); return null; }
    const chosen = await vscode.window.showQuickPick(
      hits.map((hit) => ({ label: noteTitle(hit.title), description: `#${hit.ref_id}`, detail: hit.snippet, hit })),
      { matchOnDetail: true },
    );
    return chosen ? chosen.hit : null;
  }

  command("tessellate.searchInsertLink", async () => {
    const hit = await pick();
    const editor = vscode.window.activeTextEditor;
    if (!hit || !editor) return;
    await editor.edit((edit) => edit.replace(editor.selection, `[[${noteTitle(hit.title)}]]`));
  });

  command("tessellate.searchInsertText", async () => {
    const hit = await pick();
    const editor = vscode.window.activeTextEditor;
    if (!hit || !editor) return;
    const note = await (await client()).getNote(hit.ref_id);
    await editor.edit((edit) => edit.replace(editor.selection, note.content));
  });

  command("tessellate.openNote", async (id) => {
    let target = id;
    if (!target) {
      const hit = await pick();
      if (!hit) return;
      target = hit.ref_id;
    }
    notes.delete(String(target));
    const uri = vscode.Uri.parse(`${SCHEME}:/${target}.md`);
    changed.fire(uri);
    await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(uri), { preview: true });
  });

  // VS Code's chat gets the notebook's tools over POST /mcp. Only a tool server
  // token is offered: a password session is not a tool credential, and a tool
  // token reads only unless it was made able to change notes.
  if (vscode.lm && vscode.lm.registerMcpServerDefinitionProvider && vscode.McpHttpServerDefinition) {
    context.subscriptions.push(
      toolsChanged,
      vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration("tessellate.address")) toolsChanged.fire();
      }),
      vscode.lm.registerMcpServerDefinitionProvider("tessellate.notes", {
        onDidChangeMcpServerDefinitions: toolsChanged.event,
        provideMcpServerDefinitions: async () => {
          const token = (await context.secrets.get(TOKEN_KEY)) || "";
          if (!token.startsWith(TOOL_TOKEN_PREFIX)) return [];
          const base = normaliseBase(vscode.workspace.getConfiguration("tessellate").get("address"));
          return [new vscode.McpHttpServerDefinition(
            "Tessellate notes", vscode.Uri.parse(`${base}/mcp`), { Authorization: `Bearer ${token}` },
          )];
        },
      }),
    );
  }
}

function deactivate() {}

module.exports = { activate, deactivate };
