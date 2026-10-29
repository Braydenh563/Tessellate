// appearance-panel.js: the Appearance quick panel (INBOX 1435, the owner,
// 2026-10-29: Settings, Appearance is "very large, and hard to navigate", and
// each change meant closing Settings to see it). DESIGN.md recipe
// `appearancePanel`. Lazy (`LAZY_MODULES.appearancePanel`, lazy-entries.js);
// `openAppearancePanel` is a stand-in until it loads.

//: **Moved, not copied.** The panel hosts the Appearance page's own nodes: the
//: page's children (everything but its title bar) are appended to the panel's
//: body and put back when the panel closes, so every control keeps its id, its
//: listeners and its `LOOK_ROWS` row (settings-rows.js), and the appearance
//: sync rule (tests/test_appearance_sync.py) still holds with one set of
//: controls. Fewer moving parts than a second set that has to be kept equal:
//: nothing is built twice, and the Settings page says where its controls went
//: and offers them back.
//:
//: **Non-modal.** No scrim and no focus trap; the app behind stays usable. It
//: is a `[role="dialog"]` with the dialog head, so `panelMovable` drags,
//: resizes and docks it with nothing here. The boot sheets style a setting row
//: through `#settings-modal ...`; `scripts/appearance_panel_css.py` copies those
//: rules under `#appearance-panel` (appearance-panel-lazy.css).
//:
//: **The strip** is outside the scroller, so it is always in view: a press
//: opens the section's fold and scrolls to it; the section in view is marked;
//: the last one pressed is remembered on this device. **Peek** fades the
//: panel's ground to a token mix (never element opacity), as Settings' does.
//: **Per-control reset** is the page's own `.setting-reset`, painted here with
//: the same functions Settings uses (`paintSettingRow`).
const APPEARANCE_STRIP = [
  ["theme", "Theme", '[data-fold-key="appearance-themes"]'],
  ["colour", "Colour", '[data-fold-key="appearance-colour"]'],
  ["text", "Text", "#fontsize-seg"],
  ["layout", "Layout", "#density-seg"],
  ["art", "Background art", '[data-fold-key="appearance-background"]'],
  ["motion", "Motion", "#progress-motion-row"],
];
const APPEARANCE_KEY = "appearance-panel-section";
const APPEARANCE_PANEL = { el: null, body: null, strip: null, peek: null, open: false, raf: 0, hold: 0, timers: [], opener: null };

//: Pure, so tests/test_appearance_panel.py runs it in node. `tops` are each
//: section's top in the scroller's own coordinates (null when its fold is
//: shut); the section in view is the last one that has reached `line`, else
//: the first that is there at all.
function appearanceSectionAt(tops, line) {
  let best = -1;
  tops.forEach((top, i) => {
    if (top !== null && top <= line && (best < 0 || top >= tops[best])) best = i;
  });
  if (best >= 0) return best;
  return Math.max(0, tops.findIndex((top) => top !== null));
}

function appearanceTarget(sel) {
  const el = APPEARANCE_PANEL.body?.querySelector(sel);
  return el ? el.closest("details, .setting-row") || el : null;
}

function appearanceTop(el) {
  const body = APPEARANCE_PANEL.body;
  return el.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop;
}

function appearanceMark(index) {
  APPEARANCE_PANEL.strip.querySelectorAll("button").forEach((button, i) => {
    if (i === index) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  });
}

function appearanceJump(index, smooth = true) {
  const el = appearanceTarget(APPEARANCE_STRIP[index][2]);
  if (!el) return;
  for (let fold = el.closest("details"); fold; fold = fold.parentElement?.closest("details")) fold.open = true;
  const body = APPEARANCE_PANEL.body;
  APPEARANCE_PANEL.hold = performance.now() + 700;
  body.scrollTo({ top: Math.max(0, appearanceTop(el) - 4), behavior: smooth && !reducedMotionWanted() ? "smooth" : "auto" });
  appearanceMark(index);
  prefs.set(APPEARANCE_KEY, APPEARANCE_STRIP[index][0]);
}

//: One read of seven rects per animation frame of a scroll, nothing dirty.
function appearanceSpy() {
  APPEARANCE_PANEL.raf = 0;
  if (performance.now() < APPEARANCE_PANEL.hold) return;
  const tops = APPEARANCE_STRIP.map(([, , sel]) => {
    const el = appearanceTarget(sel);
    return el && el.getClientRects().length ? appearanceTop(el) : null;
  });
  appearanceMark(appearanceSectionAt(tops, APPEARANCE_PANEL.body.scrollTop + 12));
}

//: The per-control resets and the "changed" marks, painted for the panel as
//: Settings paints its page; waits for the defaults the way Settings does.
function appearancePaintRows() {
  const body = APPEARANCE_PANEL.body;
  if (!APPEARANCE_PANEL.open) return;
  settingDefaults().then(() => {
    if (APPEARANCE_PANEL.open) settingRowsIn(body).forEach((row) => paintSettingRow(row, body));
  });
}

function appearanceSchedulePaint(delays) {
  APPEARANCE_PANEL.timers.forEach(clearTimeout);
  APPEARANCE_PANEL.timers = delays.map((ms) => setTimeout(appearancePaintRows, ms));
}

function appearanceSetPeek(on) {
  APPEARANCE_PANEL.el.classList.toggle("peeking", on);
  APPEARANCE_PANEL.peek.setAttribute("aria-pressed", String(on));
  APPEARANCE_PANEL.peek.classList.toggle("is-on", on);
}

function appearanceIcon(name) {
  const icon = document.createElement("i");
  icon.className = `ph ph-${name}`;
  icon.setAttribute("aria-hidden", "true");
  return icon;
}

function appearanceHeadButton(label, icon, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "icon-only ghost small dialog-head-btn";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.appendChild(appearanceIcon(icon));
  button.addEventListener("click", onClick);
  return button;
}

function appearanceBuild() {
  const panel = document.createElement("div");
  panel.id = "appearance-panel";
  panel.className = "appearance-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Appearance");

  const head = document.createElement("div");
  head.className = "row space-between dialog-head";
  const title = document.createElement("h2");
  title.className = "dialog-head-title";
  title.textContent = "Appearance";
  const tools = document.createElement("div");
  tools.className = "row";
  const help = appearanceHeadButton("About the Appearance panel", "question", () => {});
  help.dataset.helpFor = "appearance-panel-help";
  help.setAttribute("aria-controls", "appearance-panel-help");
  help.setAttribute("aria-expanded", "false");
  const peek = document.createElement("button");
  peek.type = "button";
  peek.className = "ghost small";
  peek.setAttribute("aria-pressed", "false");
  peek.title = "Fade the panel so you can see your changes on the app behind it";
  peek.append(appearanceIcon("eye"), " Peek");
  peek.firstChild.classList.add("ph-lead");
  peek.addEventListener("click", () => appearanceSetPeek(!panel.classList.contains("peeking")));
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  actions.append(
    appearanceHeadButton("Back to Settings", "arrow-square-in", () => {
      closeAppearancePanel();
      openSettingsModal("appearance");
    }),
    appearanceHeadButton("Close (Esc)", "x", () => closeAppearancePanel())
  );
  tools.append(help, peek, actions);
  head.append(title, tools);

  const strip = document.createElement("nav");
  strip.className = "appearance-strip";
  strip.setAttribute("aria-label", "Appearance sections");
  APPEARANCE_STRIP.forEach(([, label], i) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    button.textContent = label;
    button.addEventListener("click", () => appearanceJump(i));
    strip.appendChild(button);
  });

  const body = document.createElement("div");
  body.className = "settings-section appearance-panel-body";
  body.addEventListener("scroll", () => {
    if (!APPEARANCE_PANEL.raf) APPEARANCE_PANEL.raf = requestAnimationFrame(appearanceSpy);
  }, { passive: true });
  //: A control's own handler runs first; the marks follow what it saved.
  for (const type of ["change", "input"]) body.addEventListener(type, () => appearanceSchedulePaint([30, 500]));
  body.addEventListener("click", (event) => {
    if (event.target.closest?.(".seg button, .setting-reset")) appearanceSchedulePaint([30, 500]);
  });

  const helpBody = document.createElement("div");
  helpBody.className = "help-body hidden";
  helpBody.id = "appearance-panel-help";
  helpBody.setAttribute("role", "dialog");
  helpBody.setAttribute("aria-label", "About the Appearance panel");
  const words = document.createElement("p");
  words.textContent =
    "These are the Appearance settings from Settings, set beside the app so you see each change as you make it. " +
    "Drag the head to move the panel, a screen edge to dock it, the corner to resize it. " +
    "The strip jumps to a section and the panel opens on the last one you used. " +
    "Peek fades the panel so you can judge a colour on the app behind it. " +
    "An arrow beside a changed setting puts that setting back to its default. Esc closes the panel.";
  helpBody.appendChild(words);

  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !event.defaultPrevented && !event.target.closest?.("select, .help-body")) closeAppearancePanel();
  });
  panel.append(head, strip, body, helpBody);
  document.body.appendChild(panel);
  Object.assign(APPEARANCE_PANEL, { el: panel, body, strip, peek });
  initHelpToggles(panel);
}

//: The page's children go to the panel; its title bar stays, and under it a
//: line that says where the controls went and the way to bring them back.
function appearanceHost() {
  const pane = $("settings-appearance");
  const kept = ".settings-pane-title, .dock";
  for (const node of [...pane.children]) if (!node.matches(kept)) APPEARANCE_PANEL.body.appendChild(node);
  const note = document.createElement("div");
  note.className = "appearance-popped";
  const line = document.createElement("p");
  line.className = "muted";
  line.textContent = "Appearance is open in its own panel, so you can change things and watch the app.";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "small";
  back.textContent = "Bring it back here";
  back.addEventListener("click", () => closeAppearancePanel());
  note.append(line, back);
  pane.appendChild(note);
  pane.classList.add("appearance-popped-out");
}

function appearanceUnhost() {
  const pane = $("settings-appearance");
  pane.querySelector(":scope > .appearance-popped")?.remove();
  pane.classList.remove("appearance-popped-out");
  for (const node of [...APPEARANCE_PANEL.body.children]) pane.appendChild(node);
}

async function openAppearancePanel(section) {
  if (APPEARANCE_PANEL.open) {
    const at = APPEARANCE_STRIP.findIndex(([key]) => key === section);
    if (at >= 0) appearanceJump(at);
    return;
  }
  APPEARANCE_PANEL.opener = document.activeElement;
  //: The page's listeners live in settings-controls.js, which Settings fetches
  //: before it opens, and the rows' resets are settings-rows.js; the panel needs
  //: them just as much.
  await Promise.all([ensureModule("settingsControls"), ensureModule("panelMovable"), ensureModule("settingsUi")]).then(() => lazyScript("/js/settings-rows.js"));
  if (APPEARANCE_PANEL.open) return;
  if (!APPEARANCE_PANEL.el) appearanceBuild();
  APPEARANCE_PANEL.open = true;
  //: Settings is the other way in; the app has to be visible behind the panel.
  if (settingsModalOpen()) closeSettingsModal();
  appearanceHost();
  collapseLongSettingHints(APPEARANCE_PANEL.body);
  renderAppearance();
  APPEARANCE_PANEL.el.hidden = false;
  const remembered = APPEARANCE_STRIP.findIndex(([key]) => key === (section || prefs.get(APPEARANCE_KEY, "theme")));
  appearanceMark(Math.max(0, remembered));
  if (remembered > 0) appearanceJump(remembered, false);
  appearanceSchedulePaint([0, 400, 1200]);
  APPEARANCE_PANEL.strip.querySelector("button[aria-current]")?.focus();
}

function closeAppearancePanel() {
  if (!APPEARANCE_PANEL.open) return;
  APPEARANCE_PANEL.open = false;
  APPEARANCE_PANEL.timers.forEach(clearTimeout);
  //: A theme held under its Apply and Cancel notice ends with the panel, as it
  //: does with Settings.
  if (settingsControlState.themeHold) releaseThemeHold();
  appearanceSetPeek(false);
  appearanceUnhost();
  APPEARANCE_PANEL.el.hidden = true;
  const back = APPEARANCE_PANEL.opener;
  APPEARANCE_PANEL.opener = null;
  if (back?.isConnected) back.focus();
}
