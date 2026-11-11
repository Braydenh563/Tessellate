// desk-env.js: the few globals the companion's drawing files (avatars.js,
// atlas*.js) read from the app's own scripts, for the desktop companion's
// window (desktop-companion.html), which loads none of those. Loaded first.
// The drawing files stay as they are; each of these is something they already
// ask for behind a `typeof` guard or at runtime. Set on `window` rather than
// declared, because the app's own scripts declare the same names at top level
// (app.js, settings.js, settings-panes.js) and this page is never loaded with
// them: the global-scope lints read every file as one scope.

//: A script or stylesheet on demand, as app.js's `lazyScript` does it (the
//: rig and tail files Atlas loads when a figure mounts).
const deskFileLoads = new Map();
window.lazyScript = (file) => {
  if (!deskFileLoads.has(file)) {
    deskFileLoads.set(
      file,
      new Promise((resolve) => {
        const css = file.endsWith(".css");
        const el = document.createElement(css ? "link" : "script");
        if (css) el.rel = "stylesheet";
        else el.async = false;
        el[css ? "href" : "src"] = file;
        el.onload = () => resolve(true);
        el.onerror = () => resolve(false);
        document.head.appendChild(el);
      })
    );
  }
  return deskFileLoads.get(file);
};

//: The lazy modules the drawing asks for by name. Atlas's blink rig and tail
//: are loaded with the page (desktop-companion.html), so they answer true; the
//: companion's menu and throws are the wandering companion's, which this
//: window does not have. The capture card (Quick note) is the app's own, fetched
//: on first use as the app fetches it (`LAZY_MODULES`, lazy-entries.js).
const DESK_MODULES = ["atlasMotion", "atlasLife", "atlasFaces"];
window.ensureModule = (name) => {
  const files = { captureCard: ["/css/capture-card-lazy.css", "/js/att-chip.js", "/js/capture-card.js"] }[name];
  return files ? Promise.all(files.map((file) => window.lazyScript(file))).then((done) => done.every(Boolean)) : Promise.resolve(DESK_MODULES.includes(name));
};

//: The card's second file (colours, the bell, Draw, tag suggestions) needs the app's
//: pickers and menus, which this page has none of: the card runs on its core and on the
//: staging file (capture-stage.js: pictures and files, chips, upload on Save), which it fetches.
window.lazyScript = ((load) => (file) => (file === "/js/capture-card-more.js" ? Promise.resolve(false) : load(file)))(window.lazyScript);

//: `setLabel` for the one chip att-chip.js builds (its remove x): the glyph marker and the words.
window.setLabel = (el, label) => {
  const match = /^ph:([a-z0-9-]{1,40})\s*(.*)$/.exec(String(label ?? ""));
  if (!match) return void (el.textContent = label);
  const mark = document.createElement("i");
  mark.className = `ph ph-${match[1]}`;
  mark.setAttribute("aria-hidden", "true");
  el.replaceChildren(mark, ...(match[2] ? [document.createTextNode(match[2])] : []));
};

//: A note's title as its leading heading (`withTitle`, capture-ask.js, minus the property
//: block a desk note never has).
window.withTitle = (content, title) => ((title || "").trim() ? `# ${title.trim()}\n\n${content.replace(/^\n+/, "")}` : content);

//: The Appearance choices the app's window saved in this browser's storage
//: (the window shares it), read the way `appearancePref` reads them.
window.appearancePref = (key, fallback) => prefs.get(key, null) ?? fallback;

//: The notebook's own settings the faces read (`display_name`, `avatar_style`),
//: filled in by desk-companion.js once the notebook is open.
window.prefsCache = {};
