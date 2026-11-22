// Drives lib/client.js and extension.js under plain node for
// tests/test_vscode_extension.py. Reads one JSON job from argv:
//   {"mode": "request", ...}  print the request the client would send
//   {"mode": "reply", ...}    feed a recorded reply through the client
//   {"mode": "activate"}      activate extension.js against a stub vscode
"use strict";

const Module = require("module");
const path = require("path");
const job = JSON.parse(process.argv[2]);
const { Client } = require(path.join(__dirname, "..", "lib", "client.js"));

function reply(status, body) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

async function main() {
  if (job.mode === "request") {
    let seen;
    globalThis.fetch = async (url, init) => {
      seen = { url: String(url), method: init.method, headers: init.headers, body: JSON.parse(init.body) };
      return reply(200, { result: { content: [{ type: "text", text: "{}" }] } });
    };
    const api = new Client(job.url, job.token);
    if (job.name === "search_notes") await api.search(job.args.query, job.args.limit);
    else await api.capture(job.args.content, job.args.tags || []);
    return seen;
  }
  if (job.mode === "reply") {
    globalThis.fetch = async () => reply(job.status, job.body);
    try {
      const api = new Client(job.url, job.token);
      if (job.op === "capture") return { out: await api.capture("x") };
      return { out: await api.search("x") };
    } catch (error) {
      return { error: error.message };
    }
  }
  if (job.mode === "activate") {
    const commands = [];
    let provider = null;
    const emitter = class { constructor() { this.event = () => {}; } fire() {} dispose() {} };
    const stub = {
      EventEmitter: emitter,
      Uri: { parse: (value) => ({ value }) },
      McpHttpServerDefinition: class { constructor(label, uri, headers) { Object.assign(this, { label, uri, headers }); } },
      commands: { registerCommand: (id) => (commands.push(id), { dispose() {} }) },
      lm: { registerMcpServerDefinitionProvider: (id, p) => ((provider = { id, p }), { dispose() {} }) },
      workspace: {
        getConfiguration: () => ({ get: () => "http://127.0.0.1:8123/" }),
        onDidChangeConfiguration: () => ({ dispose() {} }),
        registerTextDocumentContentProvider: () => ({ dispose() {} }),
      },
      window: {}, env: {},
    };
    const load = Module._load;
    Module._load = function (request, ...rest) {
      return request === "vscode" ? stub : load.call(this, request, ...rest);
    };
    const ext = require(path.join(__dirname, "..", "extension.js"));
    const store = new Map(job.token ? [["tessellate.token", job.token]] : []);
    const context = { subscriptions: [], secrets: { get: async (k) => store.get(k), store: async () => {}, delete: async () => {} } };
    ext.activate(context);
    const defs = await provider.p.provideMcpServerDefinitions();
    return { commands, provider: provider.id, defs };
  }
  throw new Error(`unknown mode ${job.mode}`);
}

main().then((out) => process.stdout.write(JSON.stringify(out)), (error) => {
  process.stderr.write(String(error.stack || error));
  process.exit(1);
});
