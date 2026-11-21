"use strict";
const test = require("node:test");
const assert = require("node:assert");
const http = require("node:http");
const { Client, ApiError, noteTitle, normaliseBase } = require("../lib/client");

// A fake Tessellate: records each request, answers the routes the client uses.
function fake(handler) {
  const seen = [];
  const server = http.createServer((req, res) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      seen.push({ method: req.method, url: req.url, token: req.headers["x-auth-token"], body: raw ? JSON.parse(raw) : null });
      const [status, body] = handler(req, seen[seen.length - 1]);
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(body));
    });
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok({ server, seen, address: `127.0.0.1:${server.address().port}` })));
}

test("sign in stores the token and later calls send it", async () => {
  const { server, seen, address } = await fake((req) =>
    req.url === "/auth/unlock" ? [200, { token: "abc" }] : [200, { id: 7, content: "hi" }]);
  const client = new Client(address);
  assert.strictEqual(await client.signIn("pw"), "abc");
  assert.deepStrictEqual(seen[0].body, { password: "pw" });
  assert.strictEqual((await client.getNote(7)).id, 7);
  assert.strictEqual(seen[1].token, "abc");
  server.close();
});

test("capture posts content and tags to /entries", async () => {
  const { server, seen, address } = await fake(() => [201, { id: 3 }]);
  const note = await new Client(address, "t").capture("a thought", ["x"]);
  assert.strictEqual(note.id, 3);
  assert.deepStrictEqual(seen[0], { method: "POST", url: "/entries", token: "t", body: { content: "a thought", tags: ["x"] } });
  server.close();
});

test("search asks for notes and keeps only note hits", async () => {
  const { server, seen, address } = await fake(() => [200, { hits: [{ kind: "note", ref_id: 1, title: "A" }, { kind: "file", ref_id: 2 }] }]);
  const hits = await new Client(address, "t").search("cats", 5);
  assert.deepStrictEqual(hits.map((h) => h.ref_id), [1]);
  assert.match(seen[0].url, /^\/search\?q=cats&limit=5&kind=note$/);
  server.close();
});

test("a 401 says to sign in and a 4xx carries the detail", async () => {
  const { server, address } = await fake((req) => (req.url.startsWith("/entries/1") ? [401, {}] : [400, { detail: "No password is set yet." }]));
  const client = new Client(address);
  await assert.rejects(client.getNote(1), (e) => e instanceof ApiError && e.status === 401 && /Sign in/.test(e.message));
  await assert.rejects(client.signIn("x"), /No password is set yet/);
  server.close();
});

test("an unreachable server is a plain message", async () => {
  await assert.rejects(new Client("127.0.0.1:1").status(), /Cannot reach Tessellate/);
});

test("helpers", () => {
  assert.strictEqual(normaliseBase("localhost:8000/"), "http://localhost:8000");
  assert.throws(() => normaliseBase(" "));
  assert.strictEqual(noteTitle("\n## Heading\nbody"), "Heading");
  assert.strictEqual(noteTitle("", "x"), "x");
});
