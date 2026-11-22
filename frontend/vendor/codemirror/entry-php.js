// The PHP language, a third vendored file (php.min.js) fetched the first time a
// .php document opens (L-documents-63). Built with @codemirror/state, view,
// language and lang-html mapped to the main bundle's `window.CM6` (build.sh), so
// PHP-in-HTML reuses the editor's own HTML grammar and only the PHP grammar is
// new. Adds `CM6.php` (this namespace) to that global.
export { php, phpLanguage } from "@codemirror/lang-php";
