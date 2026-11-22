// Builds vim.min.js and php.min.js for build.sh, each with every @codemirror/*
// import resolved to the main bundle's `window.CM6`, never a second copy.
// `@codemirror/lang-html` is the bundle's `html` namespace.
import { build } from "esbuild";

const parts = new Set(["state", "view", "language", "search", "commands", "html"]);
const cm6Global = {
  name: "cm6-global",
  setup(b) {
    b.onResolve({ filter: /^@codemirror\// }, (args) => {
      if (args.path === "@codemirror/lang-php") return undefined; // the one package php.min.js exists to bundle
      const part = args.path.slice("@codemirror/".length).replace(/^lang-html$/, "html");
      if (!parts.has(part)) throw new Error(`this bundle needs ${args.path}, which CM6 does not expose`);
      return { path: part, namespace: "cm6" };
    });
    // One copy of the Lezer runtime: tag identity is what the highlighter matches on, and `instanceof Tree` must
    // hold between the HTML trees the bundle parses and the PHP ones this file does.
    b.onResolve({ filter: /^@lezer\/(highlight|common|lr)$/ }, (args) => ({ path: args.path.slice("@lezer/".length), namespace: "cm6" }));
    b.onLoad({ filter: /.*/, namespace: "cm6" }, (args) => ({ contents: `module.exports = window.CM6.${args.path};`, loader: "js" }));
  },
};

for (const [entry, globalName, outfile] of [["entry-vim.js", "CM6Vim", "vim.min.js"], ["entry-php.js", "CM6Php", "php.min.js"]]) {
  await build({
    entryPoints: [entry], bundle: true, format: "iife", globalName, minify: true,
    target: "es2020", legalComments: "none", outfile, plugins: [cm6Global],
  });
}
