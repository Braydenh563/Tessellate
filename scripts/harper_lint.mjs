// Harper (frontend/vendor/harper, Apache-2.0) over lines of text, in node:
// the composer's grammar lint at test time (O4; BACKLOG INBOX 1299, "run the
// vendored Harper grammar rules over composer output (test-time lint
// first...)"). Reads a JSON array of strings on stdin, writes a JSON array of
// [{rule, message, problem}] per string. The wasm is read from disk: node's
// fetch takes no file: URL, so the loader's fetch is answered here.
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const realFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const url = String(input?.url || input);
  if (url.startsWith("file:")) {
    const bytes = await readFile(fileURLToPath(url));
    return new Response(bytes, { headers: { "Content-Type": "application/wasm" } });
  }
  return realFetch(input, init);
};

const { Dialect } = await import("../frontend/vendor/harper/BinaryModule-BmeyZWwZ.js");
const { slimBinary } = await import("../frontend/vendor/harper/slimBinary.js");

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const texts = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const dialect = process.argv[2] === "us" ? Dialect.American : Dialect.British;
const linter = await slimBinary.createLinter(dialect);
const off = (process.argv[3] || "").split(",").filter(Boolean);
if (off.length) {
  const config = linter.get_lint_config_as_object();
  for (const rule of off) config[rule] = false;
  linter.set_lint_config_from_object(config);
}
const out = [];
for (const text of texts) {
  const lints = linter.lint(text, slimBinary.Language?.Plain ?? 0);
  out.push(
    lints.map((lint) => {
      const span = lint.span();
      return { rule: lint.lint_kind(), message: lint.message(), problem: text.slice(span.start, span.end) };
    })
  );
}
process.stdout.write(JSON.stringify(out));
