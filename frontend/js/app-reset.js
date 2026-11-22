// app-reset.js: Quit, clearing the app's caches, Reload the app, and the autonomous-tasks panel toggle
// (`quitApp`, `clearAppCache`, `forceReloadApp`, `toggleAutonomousPanel`). Moved out of phone-shell.js
// (LEDGER L698, L639) to come off the boot file: lazy, the `appReset` bundle with stand-ins in lazy-entries.js.
// Every caller is a press or a Settings handler that awaits or ignores the answer, so the stand-in's promise
// serves; the top bar's Quit button is bound in phone-shell.js to the stand-in.

// Quit, from either place it is offered: the top bar (§36D) and Settings →
// System. One handler, bound to both, rather than two copies that drift.
async function quitApp() {
  // Confirmed, because it is not undoable from inside the app: once the
  // server is down, the button that would bring it back is on the page that
  // just stopped being served.
  if (!(await confirmDialog(
    "Quit Tessellate?\n\nThe app and its server will stop. Your notes are already saved.",
    { confirmLabel: "Quit" }
  ))) {
    return;
  }
  try {
    await apiJson("/shutdown", { method: "POST" });
  } catch (error) {
    // The server may drop the connection as it goes. That is the request
    // succeeding, not failing, so it is not worth an error toast. A refusal
    // is not: another device is told why, and the app goes on running.
    if (error?.status === 403) return toast(error.message, true);
  }
  document.body.innerHTML =
    '<div class="farewell">' +
    "<h1>Tessellate has stopped.</h1>" +
    "<p>Your notes are saved. You can close this tab.</p></div>";
}
// ROADMAP item C: "several extras only take effect on restart and the app
// says so without offering one." This is that offer, a plain restart, not
// tied to any preference changing, for Settings, About.
//: The app's own caches, forgotten (INBOX 487): service worker, Cache Storage,
//: the server's compressed files. Each part is best effort; the caller reloads.
async function clearAppCache() {
  try {
    const regs = await navigator.serviceWorker?.getRegistrations?.();
    await Promise.all((regs || []).map((r) => r.unregister()));
    const keys = await window.caches?.keys?.();
    await Promise.all((keys || []).map((k) => caches.delete(k)));
  } catch {
    // Nothing to clear, or storage refused, the reload alone still helps.
  }
  try {
    await apiJson("/system/clear-static-cache", { method: "POST" });
  } catch {
    // The server's copies are rebuilt per file version anyway.
  }
}
async function forceReloadApp() {
  await clearAppCache();
  location.reload();
}

function toggleAutonomousPanel() {
  const panel = $("autonomous-settings-panel");
  if (panel) panel.classList.toggle("hidden", !$("pref-autonomous-tasks").checked);
}
