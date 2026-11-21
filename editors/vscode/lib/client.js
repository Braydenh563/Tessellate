"use strict";
// The Tessellate API client: plain Node, no VS Code import, so a node test
// can run it against a fake server. It talks to the local server only.

const ROUTES = {
  status: "/auth/status",
  unlock: "/auth/unlock",
  entries: "/entries",
  search: "/search",
};

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
    if (this.token) headers["X-Auth-Token"] = this.token;
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
      throw new ApiError(response.status, response.status === 401 ? "Sign in to Tessellate first." : detail);
    }
    return data;
  }

  status() { return this.request("GET", ROUTES.status); }

  async signIn(password) {
    const data = await this.request("POST", ROUTES.unlock, { body: { password } });
    if (!data || !data.token) throw new Error("This device is waiting for approval on the computer Tessellate runs on.");
    this.token = data.token;
    return data.token;
  }

  async capture(content, tags = []) {
    return this.request("POST", ROUTES.entries, { body: { content, tags } });
  }

  async search(q, limit = 20) {
    const data = await this.request("GET", ROUTES.search, { query: { q, limit, kind: "note" } });
    return ((data && data.hits) || []).filter((hit) => hit.kind === "note");
  }

  getNote(id) { return this.request("GET", `${ROUTES.entries}/${encodeURIComponent(id)}`); }
}

function noteTitle(content, fallback) {
  const line = String(content || "").split("\n").map((l) => l.replace(/^#+\s*/, "").trim()).find(Boolean);
  return (line || fallback || "Untitled").slice(0, 80);
}

module.exports = { Client, ApiError, ROUTES, noteTitle, normaliseBase };
