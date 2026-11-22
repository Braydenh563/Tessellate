"use strict";
// The Tessellate API client: plain Node, no VS Code import, so a node test
// can run it against a fake server. It talks to the local server only.

const ROUTES = {
  status: "/auth/status",
  unlock: "/auth/unlock",
  entries: "/entries",
  search: "/search",
  tools: "/mcp",
};

//: A tool server token from Settings, Tools it can use (L-world-class-627):
//: it does not idle out like a session, it is limited to the categories and
//: tags it was made for, reads only unless it was made able to change notes,
//: and is revoked there. With one, every call goes through /mcp's tools.
const TOOL_TOKEN_PREFIX = "tsl_mcp_";

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `The server answered ${status}.`);
    this.status = status;
  }
}

function normaliseBase(address) {
  let base = String(address || "").trim().replace(/\/+$/, "");
  if (!base) throw new Error("Set the Tessellate address first.");
  if (!/^https?:\/\//i.test(base)) base = "http://" + base;
  return base;
}

class Client {
  constructor(address, token) {
    this.base = normaliseBase(address);
    this.token = token || "";
  }

  async request(method, path, { query, body } = {}) {
    const url = new URL(this.base + path);
    for (const [key, value] of Object.entries(query || {})) url.searchParams.set(key, String(value));
    const headers = { Accept: "application/json" };
    if (this.usesTools) headers.Authorization = `Bearer ${this.token}`;
    else if (this.token) headers["X-Auth-Token"] = this.token;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let response;
    try {
      response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (error) {
      throw new Error(`Cannot reach Tessellate at ${this.base}. Is it running?`);
    }
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (_) { data = null; }
    if (!response.ok) {
      const detail = data && typeof data.detail === "string" ? data.detail : "";
      const signIn = this.usesTools ? "Tessellate refused this token. Make a new one in Settings, Tools it can use." : "Sign in to Tessellate first.";
      throw new ApiError(response.status, response.status === 401 ? signIn : detail);
    }
    return data;
  }

  get usesTools() { return this.token.startsWith(TOOL_TOKEN_PREFIX); }

  async tool(name, args) {
    const data = await this.request("POST", ROUTES.tools, { body: { jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } } });
    if (data && data.error) throw new Error(data.error.message || "The tool server refused the call.");
    const text = (data && data.result && data.result.content && data.result.content[0] && data.result.content[0].text) || "";
    if (data.result.isError) throw new Error(text || "The tool server refused the call.");
    try { return JSON.parse(text); } catch (_) { return { text }; }
  }

  //: Checks a pasted token before it is kept: a wrong or revoked one is 401.
  async useToken(token) {
    const pasted = String(token || "").trim();
    if (!pasted.startsWith(TOOL_TOKEN_PREFIX)) throw new Error("That is not a Tessellate tool server token. Copy it from Settings, Tools it can use.");
    this.token = pasted;
    await this.request("POST", ROUTES.tools, { body: { jsonrpc: "2.0", id: 1, method: "tools/list", params: {} } });
    return pasted;
  }

  status() { return this.request("GET", ROUTES.status); }

  async signIn(password) {
    const data = await this.request("POST", ROUTES.unlock, { body: { password } });
    if (!data || !data.token) throw new Error("This device is waiting for approval on the computer Tessellate runs on.");
    this.token = data.token;
    return data.token;
  }

  async capture(content, tags = []) {
    if (this.usesTools) return this.tool("create_note", { content, tags });
    return this.request("POST", ROUTES.entries, { body: { content, tags } });
  }

  async search(q, limit = 20) {
    if (this.usesTools) {
      //: The tool answers at most ten, as previews; shaped like /search's hits.
      const data = await this.tool("search_notes", { query: q, limit: Math.min(limit, 10) });
      return ((data && data.notes) || []).map((note) => ({
        kind: "note", ref_id: note.id, title: noteTitle(note.content, `Note ${note.id}`), snippet: String(note.content || "").slice(0, 200),
      }));
    }
    const data = await this.request("GET", ROUTES.search, { query: { q, limit, kind: "note" } });
    return ((data && data.hits) || []).filter((hit) => hit.kind === "note");
  }

  getNote(id) {
    if (this.usesTools) return this.tool("get_note", { note_id: Number(id) });
    return this.request("GET", `${ROUTES.entries}/${encodeURIComponent(id)}`);
  }
}

function noteTitle(content, fallback) {
  const line = String(content || "").split("\n").map((l) => l.replace(/^#+\s*/, "").trim()).find(Boolean);
  return (line || fallback || "Untitled").slice(0, 80);
}

module.exports = { Client, ApiError, ROUTES, TOOL_TOKEN_PREFIX, noteTitle, normaliseBase };
