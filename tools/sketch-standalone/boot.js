// Quick sketch on a page of its own: the pad with a small host (localStorage
// for its settings, the browser's confirm, Download PNG, no save to notes).
// The app's light and dark tokens follow the system setting.
(function () {
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  const theme = () => { document.documentElement.dataset.mode = dark.matches ? "dark" : "light"; };
  theme();
  dark.addEventListener("change", theme);
  //: The settings (colours, recent colours, paper, size) kept between visits.
  //: Storage can throw in a private window; the setting then lasts the visit.
  const prefs = {
    get(key, fallback) {
      try {
        const raw = window.localStorage.getItem(`sketch-pad:${key}`);
        return raw === null ? fallback : JSON.parse(raw);
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        window.localStorage.setItem(`sketch-pad:${key}`, JSON.stringify(value));
      } catch {
        /* blocked storage: nothing to keep */
      }
    },
  };
  window.SketchPad.open(document.getElementById("sketch-card"), { title: "Quick sketch", prefs });
})();
