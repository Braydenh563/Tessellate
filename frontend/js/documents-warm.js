// documents-warm.js: first file of the Library bundle (L-documents-83). The cold
// open of Documents was a chain: the bundle's 35 scripts (about 300 ms to
// arrive, 250 more to run), then the list, then the document, then the editor
// engine. Every link after the first waited for code that does not need to
// run first, so this file, which arrives and runs ahead of the rest, starts
// them: the list, the file-type table, the engine and the IDE file are
// requested while the bundle is still being fetched, and the first
// document is asked for as soon as the list names it. Only when the Documents
// tab is the one on screen: a note box's first focus loads this bundle too.
//
// **How a caller gets the answer.** `api` is wrapped, here and not in app.js
// (the boot gzip cap has no room for it): a read for a path asked for below is
// answered with that request, once, and an answer nobody took within 4 s is
// dropped. The wrapper keeps `api`'s own properties (`epoch`, `retries`,
// `upload`), and a write never matches.
(() => {
  if (document.getElementById("tab-documents")?.classList.contains("hidden") !== false) return;
  const warm = {};
  const real = api;
  api = Object.assign((path, options) => (!options?.method && warm[path]?.()) || real(path, options), real);
  const ask = (path, options) => {
    const pending = api(path, options);
    warm[path] = () => (delete warm[path], pending);
    pending.catch(() => delete warm[path]);
    setTimeout(() => delete warm[path], 4000);
    return pending;
  };
  const preload = (href) => document.head.appendChild(Object.assign(document.createElement("link"), { rel: "preload", as: "script", href }));
  preload("/vendor/codemirror/codemirror.min.js");
  preload("/js/documents-ide.js" + lazyAssetStamp("/js/documents-ide.js"));
  ask("/documents/file-types", { silent: true });
  ask(`/documents?limit=${DOCUMENTS_PAGE_SIZE}&offset=0`)
    .then((response) => response.clone().json())
    .then((rows) => Array.isArray(rows) && rows[0] && ask(`/documents/${rows[0].id}`))
    .catch(() => {});
})();
