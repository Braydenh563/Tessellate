// Quick sketch on a page of its own: the pad with its built-in host
// (localStorage for its settings, the browser's confirm, Download PNG, no
// save to notes). The app's light and dark tokens follow the system setting.
(function () {
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  const theme = () => { document.documentElement.dataset.mode = dark.matches ? "dark" : "light"; };
  theme();
  dark.addEventListener("change", theme);
  window.SketchPad.open(document.getElementById("sketch-card"), { title: "Quick sketch" });
})();
