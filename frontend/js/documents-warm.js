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
//
// **A file that throws at load** stops the rest of the bundle's one script
// (L-documents-119). The route appends `lazyFileLoads.set("#at", n)` after each
// file (n files have finished), and `ensureModule` calls the `#f` set here
// with the load results once the script is in: the files after the
// faulty one (it ran in part; running it again would repeat its effects) are
// loaded one by one. Nothing ran when `#at` is unset (a syntax error), so all
// are. When the bundle itself failed, the files it aliased are forgotten so a retry
// fetches them. Here, not in app.js, for the boot gzip cap.
lazyFileLoads.set("#f", (r) => {
  const js = LAZY_MODULES.library.filter((f, i) => i && f.endsWith(".js"));
  return r.every(Boolean)
    ? Promise.all(js.slice(lazyFileLoads.get("#at") + 1 || 0).map((f) => (lazyFileLoads.delete(f), lazyScript(f))))
    : (js.map((f) => lazyFileLoads.delete(f)), r);
});
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
