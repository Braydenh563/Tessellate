// Drives client.js and extension.js under plain node for
// tests/test_vscode_extension.py. Reads one JSON job from argv:
//   {"mode": "request", ...}  print the request client.call would send
//   {"mode": "reply", ...}    feed a recorded reply through client.call and noteItems
//   {"mode": "activate"}      activate extension.js against a stub vscode
"use strict";

const Module = require("module");
const path = require("path");
const job = JSON.parse(process.argv[2]);
const client = require(path.join(__dirname, "..", "client.js"));

async function main() {
  if (job.mode === "request") {
    let seen;
    const fake = async (url, init) => {
      seen = { url, method: init.method, headers: init.headers, body: JSON.parse(init.body) };
      return { ok: true, status: 200, json: async () => ({ result: { content: [{ type: "text", text: "{}" }] } }) };
    };
    await client.call(job.url, job.token, job.name, job.args, fake);
    return seen;
  }
  if (job.mode === "reply") {
    const fake = async () => ({ ok: job.status === 200, status: job.status, json: async () => job.body });
    try {
      const out = await client.call(job.url, job.token, "search_notes", {}, fake);
      return { out, items: client.noteItems(out), link: client.noteLink(job.url, 7) };
    } catch (error) {
      return { error: error.message, typed: error instanceof client.ToolServerError };
    }
  }
  if (job.mode === "activate") {
    const commands = [];
    let provider = null;
    const stub = {
      EventEmitter: class { constructor() { this.event = () => {}; } fire() {} dispose() {} },
      Uri: { parse: (value) => ({ value }) },
      McpHttpServerDefinition: class { constructor(label, uri, headers) { Object.assign(this, { label, uri, headers }); } },
      commands: { registerCommand: (id) => (commands.push(id), { dispose() {} }) },
      lm: { registerMcpServerDefinitionProvider: (id, p) => ((provider = { id, p }), { dispose() {} }) },
      workspace: {
        getConfiguration: () => ({ get: () => "http://127.0.0.1:8123/" }),
        onDidChangeConfiguration: () => ({ dispose() {} }),
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
