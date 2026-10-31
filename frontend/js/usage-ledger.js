// Settings, General: Simple mode and What you use (WORLD_CLASS_PLAN H9,
// row 27). Loaded when that section opens (settings.js).
//
// What you use reads the local usage ledger (core/usage.py, counted by
// `usageCount` in navigation.js): the most used tabs and commands on one
// facts line, and the ones not used in ninety days, which is the list a
// person can act on. The known features are this page's own: its tabs and
// its palette commands, so a command never run at all is named too.
//
// Simple mode is a per-device switch (`simpleMode` in localStorage, read by
// theme-boot.js before first paint): `data-simple="on"` on <html> hides the
// tabs and settings a new person does not need (08-consistency.css lists
// them). Every hidden place still opens from the palette.

const USAGE_TABS = ["dashboard", "notes", "chat", "graph", "library", "timeline", "reminders"];
const SIMPLE_HIDDEN_TABS = ["graph", "timeline", "reminders"];

function usageLabels() {
  const labels = {};
  for (const tab of USAGE_TABS) {
    const button = document.querySelector(`#tab-bar button[data-tab="${tab}"]`);
    labels[`tab:${tab}`] = `${(button?.textContent || tab).trim()} tab`;
  }
  for (const command of paletteCommands()) {
    const name = usageFeatureName(command.label);
    if (name && !labels[name]) labels[name] = String(command.label).replace(/(^|\s)ph:[\w-]+/g, " ").trim();
  }
  return labels;
}

async function renderUsage() {
  renderSimpleMode();
  const most = $("usage-most");
  const unused = $("usage-unused");
  if (!most) return;
  const labels = usageLabels();
  let summary;
  try {
    summary = await apiJson("/usage/summary", { method: "POST", body: JSON.stringify({ known: Object.keys(labels) }) });
  } catch {
    surfaceFailed(most, "your usage counts", renderUsage);
    return;
  }
  surfaceRecovered(most);
  const top = summary.features.slice(0, 5).map((f) => `${labels[f.name] || f.name} ${f.count}`);
  most.textContent = top.length ? `Most used: ${top.join(" · ")}` : "Nothing counted yet.";
  const names = summary.unused.map((n) => labels[n] || n);
  unused.textContent = names.length
    ? `Not used in ${nounCount(summary.unused_days, "day")} (${names.length}): ${names.slice(0, 12).join(", ")}${names.length > 12 ? ", and more" : ""}.`
    : `Everything here was used in the last ${nounCount(summary.unused_days, "day")}.`;
}

function applySimpleMode(on) {
  if (on) document.documentElement.dataset.simple = "on";
  else delete document.documentElement.dataset.simple;
  try {
    prefs.set("simpleMode", on ? "1" : "0");
  } catch {
    // A private window can refuse storage; the mode still applies for now.
  }
  //: The tab in front would vanish under the person: go to the dashboard.
  if (on && SIMPLE_HIDDEN_TABS.includes(prefs.get("activeTab", null))) switchTab("dashboard");
}

function renderSimpleMode() {
  const box = $("pref-simple-mode");
  if (box) box.checked = document.documentElement.dataset.simple === "on";
}

//: Settings, Keyboard shortcuts, Capture from anywhere: the exact command for
//: this install (`GET /capture/command`), and its Copy.
async function renderCaptureCommand() {
  const code = $("capture-command");
  if (!code) return;
  const reply = await apiJson("/capture/command", { silent: true }).catch(() => null);
  if (reply && reply.command) code.textContent = reply.command;
}

$("capture-command-copy")?.addEventListener("click", async () => {
  //: Through the shared helper, which falls back where the clipboard API
  //: is not allowed (tests/test_log_console.py).
  if (await copyToClipboard($("capture-command").textContent)) toast("Copied. Paste it as the command your shortcut runs.");
  else toast("Couldn't copy here. Select the command and copy it.", "info");
});

$("pref-simple-mode")?.addEventListener("change", (event) => applySimpleMode(event.target.checked));
$("usage-clear")?.addEventListener("click", async () => {
  try {
    await apiJson("/usage", { method: "DELETE" });
    //: And the palette's learned order, which is the same habit kept per
    //: browser (app-palette.js `palettePick`, Brief 90).
    prefs.remove("palette-picks");
    toast("Every count is cleared.");
  } catch (error) {
    toast(error.message || "Couldn't clear the counts.", true);
  }
  renderUsage();
});

//: **What fills the window, by part** (the owner, 2026-10-10: "i expect to see
//: a dropdown to see my token distribution stats"). From the turn's own
//: `stats.composition` (agent.py and routes_chat.py estimate it at four
//: characters a token, the budgeter's own rate), so the parts say "about";
//: the total is the model's count when it reported one. Here, not in
//: chat.js, for the boot scripts' gzip ratchet (test_static_compression.py).
function renderChatContextPop(stats, used, window, pct) {
  const parts = stats.composition || {};
  $("chat-context-pop-total").textContent = `${compactTokens(used)} of ${compactTokens(window)} tokens (${pct}%)`;
  $("chat-context-pop-fill").style.width = `${pct}%`;
  $("chat-context-pop-rows").textContent = [["notes", "Your notes and the question"], ["history", "Earlier turns"], ["tool_schemas", "Tools"], ["system", "Instructions"]]
    .filter(([key]) => parts[key])
    .map(([key, label]) => `${label}: about ${compactTokens(parts[key])}`)
    .join("\n");
}

//: The pill opens what fills the window, and the thing that fixes it is the
//: popover's one action: a number with no move attached is a number people
//: learn to ignore, and a number that silently compacted the chat when
//: pressed was the other mistake (the owner, 2026-10-10). chat.js loads this
//: file when the pill first shows, so the popover is wired before it can be
//: pressed. Its stylesheet is fetched from here rather than listed in
//: `LAZY_MODULES`: app.js is at its own gzip cap (APP_JS_CAP).
wireHelpPopover($("chat-context"), $("chat-context-pop"));
$("chat-context-compact").addEventListener("click", () => {
  closeHelpPopovers();
  $("chat-compress").click();
});
$("chat-context-window").addEventListener("click", () => {
  closeHelpPopovers();
  openSettingsModal("models", "model-context-window");
});
