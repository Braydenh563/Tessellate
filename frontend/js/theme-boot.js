// Everything visual is applied before first paint, so the app never
// flashes the default look and then corrects itself.
//
// The lookup order matches appearancePref() in app.js exactly:
//     your manual change  →  the selected theme  →  the app default
// It is duplicated here rather than imported because app.js loads at the
// end of the body, which is far too late to prevent the flash. The theme
// VALUES are the only thing repeated; keep them in step with
// THEME_PRESETS, or a themed reload will flicker.
(function () {
  const _r = document.documentElement;
  const THEMES = {
    utilitarian: { palette: "utilitarian", glass: "off", radius: "8" },
    paper: { palette: "paper", glass: "off", radius: "4" },
    mono: { palette: "mono", glass: "off", radius: "2", density: "compact" },
    default: { palette: "default", glass: "on", radius: "14" },
    manuscript: { palette: "parchment", font: "serif", glass: "off", radius: "6", density: "spacious" },
    terminal: { palette: "carbon", font: "mono", glass: "off", radius: "2", density: "compact" },
    study: { palette: "sage", font: "serif", glass: "on", radius: "16" },
    abyss: { palette: "ocean", glass: "on", "glass-blur": "26", radius: "14" },
    ember: { palette: "ember", glass: "on", radius: "12" },
    orchid: { palette: "plum", glass: "on", radius: "18" },
    blueprint: { palette: "ocean", font: "mono", glass: "off", radius: "4", density: "compact" },
    graphite: { palette: "carbon", glass: "off", radius: "4" },
    lagoon: { palette: "lagoon", glass: "on", radius: "14" },
    midnight: { palette: "midnight", glass: "on", radius: "12" },
    rosewood: { palette: "rosewood", font: "serif", glass: "on", radius: "16" },
  };
  // No look chosen means the default look, Quiet utilitarian (settings.js
  // `DEFAULT_THEME_PRESET`); an explicit choice, "default" (Classic)
  // included, is kept.
  const themePreset = localStorage.getItem("themePreset");
  const preset = THEMES[themePreset ?? "utilitarian"] || {};
  const pref = (key, fallback) =>
    localStorage.getItem(key) ?? preset[key] ?? fallback;

  // Simple mode (Settings, General; usage-ledger.js), before first paint so
  // the hidden tabs never flash in.
  if (localStorage.getItem("simpleMode") === "1") _r.dataset.simple = "on";
  const theme = pref("theme", "system");
  if (theme && theme !== "system") _r.dataset.theme = theme;
  // data-mode is the RESOLVED light/dark, which the palettes match on, 
  // under "System" there is no data-theme for CSS to hang off, so without
  // this every palette would paint its light set on a dark desktop until
  // app.js caught up.
  _r.dataset.mode =
    theme === "light" || theme === "dark"
      ? theme
      : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

  _r.dataset.pageWash = pref("page-wash", "on");
  const palette = pref("palette", "default");
  if (palette && palette !== "default") _r.dataset.palette = palette;
  const accent = pref("accent", "indigo");
  if (accent && accent !== "indigo") _r.dataset.accent = accent;
  if (localStorage.getItem("contrast") === "on") _r.dataset.contrast = "on";

  _r.dataset.fontsize = pref("fontsize", "normal");
  _r.dataset.font = pref("font", "system");
  //: **Height-aware density** (WORLD_CLASS_PLAN 22.1 item 2): with no
  //: density chosen, a window 700px tall or less is Compact, the laptop
  //: whose screen was mostly chrome. A choice in Appearance always wins.
  //: Mirrored by `effectiveDensity` in settings.js; keep the two in step.
  _r.dataset.density = localStorage.getItem("density")
    || (window.matchMedia("(max-height: 700px)").matches ? "compact" : pref("density", "comfortable"));
  // Performance mode, mirrored from perfModeOn() in settings.js: "on", or
  // "auto" on a small machine (2 cores or 4 GB or fewer), or the operating
  // system asking for less transparency. It takes the glass and the motion
  // off before first paint so a small laptop never draws the blurred frame
  // it is about to be spared. Keep the three readings in step.
  const perfPref = pref("perf", "auto");
  const small =
    (navigator.deviceMemory && navigator.deviceMemory <= 4) ||
    (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2);
  const lessGlass = window.matchMedia("(prefers-reduced-transparency: reduce)").matches;
  const perf = perfPref === "on" || (perfPref === "auto" && (small || lessGlass));
  _r.dataset.perf = perf ? "on" : "off";
  _r.dataset.glass = perf ? "off" : pref("glass", "on");
  _r.dataset.motion = perf ? "reduced" : pref("motion", "auto");
  _r.dataset.uiMotion = pref("ui-motion", "on");
  // The blankets for these two switches are a sheet that matches only while one is on (motion-still.css).
  const stillSheet = document.getElementById("motion-still-sheet");
  if (stillSheet) stillSheet.media = _r.dataset.motion === "reduced" || _r.dataset.uiMotion === "off" ? "all" : "(prefers-reduced-motion: reduce)";
  _r.dataset.themePreset = themePreset || "";
  _r.style.setProperty("--radius", pref("radius", "14") + "px");
  _r.style.setProperty("--glass-blur", pref("glass-blur", "14") + "px");
  _r.style.setProperty("--bg-art-opacity", Number(pref("bg-intensity", "45")) / 100);
  const page = pref("page-bg", null);
  if (page) _r.style.setProperty("--page", page);
})();
