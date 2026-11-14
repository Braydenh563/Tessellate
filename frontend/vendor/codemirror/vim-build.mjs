// Builds vim.min.js for build.sh: the Vim keymap with every @codemirror/*
// import resolved to the main bundle's `window.CM6`, never a second copy.
import { build } from "esbuild";

const parts = new Set(["state", "view", "language", "search", "commands"]);
const cm6Global = {
  name: "cm6-global",
  setup(b) {
    b.onResolve({ filter: /^@codemirror\// }, (args) => {
      const part = args.path.slice("@codemirror/".length);
      if (!parts.has(part)) throw new Error(`vim.min.js needs ${args.path}, which CM6 does not expose`);
      return { path: part, namespace: "cm6" };
    });
    b.onLoad({ filter: /.*/, namespace: "cm6" }, (args) => ({ contents: `module.exports = window.CM6.${args.path};`, loader: "js" }));
  },
};

await build({
  entryPoints: ["entry-vim.js"], bundle: true, format: "iife", globalName: "CM6Vim", minify: true,
  target: "es2020", legalComments: "none", outfile: "vim.min.js", plugins: [cm6Global],
});
