// The CodeMirror 6 surface MemoryMap vendors: one IIFE, one global (`CM6`),
// every module the editor needs and nothing it does not. Rebuilt by
// frontend/vendor/codemirror/build.sh; versions pinned in package.json there.
export * as state from "@codemirror/state";
export * as view from "@codemirror/view";
export * as commands from "@codemirror/commands";
export * as search from "@codemirror/search";
export * as language from "@codemirror/language";
export * as autocomplete from "@codemirror/autocomplete";
export * as lint from "@codemirror/lint";
export * as markdown from "@codemirror/lang-markdown";
export * as javascript from "@codemirror/lang-javascript";
export * as python from "@codemirror/lang-python";
export * as css from "@codemirror/lang-css";
export * as html from "@codemirror/lang-html";
export * as json from "@codemirror/lang-json";
export * as yaml from "@codemirror/lang-yaml";
export * as highlight from "@lezer/highlight";
export { shell } from "@codemirror/legacy-modes/mode/shell";
export { sql, standardSQL } from "@codemirror/legacy-modes/mode/sql";
export { toml } from "@codemirror/legacy-modes/mode/toml";
export { go } from "@codemirror/legacy-modes/mode/go";
export { rust } from "@codemirror/legacy-modes/mode/rust";
export { c, cpp, csharp, java, kotlin } from "@codemirror/legacy-modes/mode/clike";
export { ruby } from "@codemirror/legacy-modes/mode/ruby";
export { xml } from "@codemirror/legacy-modes/mode/xml";
export { diff } from "@codemirror/legacy-modes/mode/diff";
export { dockerFile } from "@codemirror/legacy-modes/mode/dockerfile";
// Added 2026-09-09 for three of the file types `GET /documents/file-types`
// already offers and the editor could not highlight. Measured cost for the
// three together: +7,658 bytes raw, +2,476 gzipped, under 1% of the bundle.
// `properties` is the INI mode; CodeMirror has no mode called `ini`.
export { swift } from "@codemirror/legacy-modes/mode/swift";
export { r } from "@codemirror/legacy-modes/mode/r";
export { properties } from "@codemirror/legacy-modes/mode/properties";
// PHP is not here: it is the lazy php.min.js (entry-php.js, L-documents-63), 28,381 bytes gzipped that only a
// .php file wants.
// Added 2026-10-10 (Brief 42, each sized before it landed, gzip -9 against
// this bundle): the merge view, to compare the editor with a saved version
// and take or undo one hunk (+29,294 raw, +10,014 gzipped); the minimap, off
// by default (+15,676, +5,235); Visual Basic and VBScript, two legacy modes
// (+9,926, +3,340). Indentation markers were measured too (+1,647) and left
// out: `docIndentGuides` in documents-code.js already draws them.
export * as merge from "@codemirror/merge";
export { showMinimap } from "@replit/codemirror-minimap";
export { vb } from "@codemirror/legacy-modes/mode/vb";
export { vbScript } from "@codemirror/legacy-modes/mode/vbscript";
// Added 2026-11-14 (L-documents-63): the Lezer runtime, so the lazy php.min.js
// shares one copy of Tree, TreeBuffer and parseMixed with this bundle (PHP is
// embedded in HTML, and two copies of @lezer/common break `instanceof` between
// the HTML trees here and the PHP ones there). Measured: +413 bytes raw, +207
// gzipped.
export * as common from "@lezer/common";
export * as lr from "@lezer/lr";
