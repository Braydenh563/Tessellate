// The app's two lazy loaders (app.js `lazyScript` and `ensureModule`), for the
// files the renderers fetch on first use. The benches load the renderers
// without app.js, so these stand in; `LAB_MODULES` names every module the
// renderers ask for (tests/test_tools_benches.py checks it against app.js).
const LAB_ROOT = location.protocol === "file:" ? "../frontend/" : "/";
const LAB_MODULES = {
  atlasMotion: ["/js/atlas-motion.js"],
  atlasFaces: ["/css/atlas-lazy.css"],
  atlasLife: ["/js/atlas-motion.js", "/js/atlas-life.js"],
  companionMenu: ["/js/companion-menu.js"],
  companionThrow: ["/css/companion-throw-lazy.css", "/js/companion-throw.js"],
};
const labLoaded = new Map();
function lazyScript(file) {
  const src = LAB_ROOT + String(file).replace(/^\//, "");
  if (!labLoaded.has(src)) {
    labLoaded.set(src, new Promise((ok) => {
      const css = src.endsWith(".css");
      const el = document.createElement(css ? "link" : "script");
      if (css) { el.rel = "stylesheet"; el.href = src; } else el.src = src;
      el.onload = () => ok(true);
      el.onerror = () => ok(false);
      document.head.appendChild(el);
    }));
  }
  return labLoaded.get(src);
}
function ensureModule(name) {
  const files = LAB_MODULES[name];
  if (!files) return Promise.reject(new Error(`the bench has no module ${name}`));
  return files.reduce((chain, file) => chain.then(() => lazyScript(file)), Promise.resolve());
}
