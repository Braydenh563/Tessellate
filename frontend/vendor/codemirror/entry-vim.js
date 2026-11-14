// The opt-in Vim keymap, a second vendored file (vim.min.js) fetched only when
// the preference is on. It is built with every @codemirror/* package mapped to
// the main bundle's `window.CM6` (build.sh), so there is one copy of state and
// view: a second copy would break `instanceof` and facet identity. Adds
// `CM6.vim` (the extension) and `CM6.Vim` (for `:` commands) to that global.
export { vim, Vim, getCM } from "@replit/codemirror-vim";
