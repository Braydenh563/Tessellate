// The tool server client: one JSON-RPC call to `POST /mcp` per request, the
// same door and token every other MCP client uses (docs/MCP.md). Kept free of
// the `vscode` module so tests/test_vscode_extension.py runs it under plain node.
"use strict";

const NO_TOKEN = "Set a tool server token first: Settings, Tools it can use, then Tessellate: Set tool server token.";

class ToolServerError extends Error {}

function base(url) {
  return String(url || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

async function call(url, token, name, args, fetchImpl = globalThis.fetch) {
  if (!token) throw new ToolServerError(NO_TOKEN);
  let reply;
  try {
    reply = await fetchImpl(`${base(url)}/mcp`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
    });
  } catch {
    throw new ToolServerError(`Tessellate is not answering at ${base(url)}. Start the app, or change tessellate.url.`);
  }
  if (reply.status === 401) throw new ToolServerError("That token was refused. Make a new one in Settings, Tools it can use.");
  if (reply.status === 403) throw new ToolServerError("The tool server answers only on this computer unless LAN mode is on.");
  if (!reply.ok) throw new ToolServerError(`The tool server answered ${reply.status}.`);
  const body = await reply.json();
  if (body.error) throw new ToolServerError(body.error.message || "The tool server refused that call.");
  const text = body.result?.content?.find((part) => part.type === "text")?.text || "{}";
  if (body.result?.isError) throw new ToolServerError(text);
  try {
    return JSON.parse(text);
  } catch {
    return { text };
  }
}

// One quick-pick row per note: the first line as the label, the category and
// tags as the description, the rest of the preview as the detail.
function noteItems(found) {
  return (found?.notes || []).map((note) => {
    const lines = String(note.content || "").split("\n").filter((line) => line.trim());
    const head = (lines[0] || "Untitled note").slice(0, 80);
    const tags = (note.tags || []).map((tag) => `#${tag}`).join(" ");
    return {
      label: head,
      description: [note.category, tags].filter(Boolean).join("  "),
      detail: lines.slice(1).join(" ").slice(0, 160) || undefined,
      id: note.id,
    };
  });
}

function noteLink(url, id) {
  return `${base(url)}/#/notes/${encodeURIComponent(id)}`;
}

module.exports = { call, noteItems, noteLink, base, ToolServerError, NO_TOKEN };
