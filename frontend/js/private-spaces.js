// private-spaces.js: private spaces in the window (INBOX 1727). Lazy: the
// first switch into a private space, the Edit space dialog, or a move out of
// one loads it (`LAZY_MODULES.privateSpaces`, lazy-entries.js). One name in
// the shared scope, `privateSpaces(action, ...)`, since the scope is at its cap.
//
// The server holds the lock (core/spacelock.py): a locked private space is
// out of every read. This file asks for the vault password (or the PIN, on
// this computer), reports the person's own input so the idle minutes count
// only real idleness, locks on close, and asks the two-way question when
// something leaves a private space.
(() => {
  const state = { status: null, touched: 0, watching: false };

  //: Locking or unlocking changes which notes the whole notebook shows, so the one full re-read is here.
  const reread = () => loadEntries().catch(() => {});

  async function status() {
    state.status = await apiJson("/private-spaces/status", { silent: true }).catch(() => null);
    return state.status;
  }

  //: The lock card in its prompt mode, the recipe every password prompt here uses.
  async function unlock() {
    const known = await status();
    const asked = askPasswordPrompt({
      title: "Unlock private spaces",
      message: known?.pin
        ? "Your vault password or your PIN opens every private space."
        : "Your vault password opens every private space.",
      submitLabel: "Unlock",
      submit: (secret) =>
        apiJson("/private-spaces/unlock", { method: "POST", body: JSON.stringify({ secret }), ownsAuthErrors: true }),
    });
    if (known?.pin) {
      $("lock-password").placeholder = "Password or PIN";
      $("lock-password").setAttribute("aria-label", "Password or PIN");
    }
    //: Windows Hello's button on this card while it is asking (hello-unlock.js).
    if (known?.hello) ACTIONS.hello?.("space", asked);
    if (!(await asked)) return false;
    //: `watch` reads the touch against this.
    state.status = { ...(state.status || {}), open: true };
    vaultOpen = true;
    state.touched = Date.now();
    watch();
    toast("Private spaces unlocked.");
    await reread();
    return true;
  }

  async function enter() {
    const known = await status();
    if (known?.open) return watch() || true;
    return unlock();
  }

  //: The person's own input keeps them open, at most one report a minute;
  //: the app's polls never do. The report's answer is how the window learns
  //: the server locked them meanwhile (no timer of its own: wake-source lint).
  function watch() {
    if (state.watching) return;
    state.watching = true;
    const report = async () => {
      if (Date.now() - state.touched < 60e3) return;
      state.touched = Date.now();
      const was = state.status?.open;
      const now = await apiJson("/private-spaces/touch", { method: "POST", silent: true }).catch(backgroundWriteFailed);
      if (!now) return;
      state.status = { ...(state.status || {}), open: now.open };
      if (was && !now.open) {
        await reread();
        toastAction("Private spaces locked.", "Unlock", unlock);
      }
    };
    for (const kind of ["pointerdown", "keydown", "wheel"]) document.addEventListener(kind, report, { passive: true, capture: true });
  }

  //: Two answers and a way out: "Keep it private" is the default and holds
  //: the focus (the dialog's Cancel), Escape leaves with nothing changed.
  async function askKeep(noun) {
    const answer = await confirmDialog(
      `Keep ${noun} private?\n\nOutside the private space it stays sealed unless you make it ordinary.`,
      { confirmLabel: "Make it ordinary", cancelLabel: "Keep it private", danger: false }
    );
    return answer === undefined ? null : answer === false;
  }

  async function setPrivate(space, on) {
    let body = { private: on };
    if (on) {
      const counts = await apiJson(`/spaces/${encodeURIComponent(space.id)}/counts`).catch(() => ({}));
      const n = (counts.notes || 0) + (counts.documents || 0);
      const ok = await confirmDialog(
        `Make ${space.name} private?\n\n${n === 1 ? "The 1 item" : `The ${n} items`} in it ${n === 1 ? "is" : "are"} sealed with your vault password, and stay out of search, the graph, Atlas and exports while it is locked.`,
        { confirmLabel: "Make it private", danger: false }
      );
      if (!ok) return false;
    } else {
      const keep = await askKeep("everything in it");
      if (keep === null) return false;
      body = { private: false, keep_private: keep };
    }
    const send = () => api(`/spaces/${encodeURIComponent(space.id)}/private`, { method: "PUT", body: JSON.stringify(body) });
    let answer = await send();
    if (answer.status === 423 && (await unlock())) answer = await send();
    if (!answer.ok) throw new Error((await answer.json().catch(() => ({})))?.detail?.detail || "Couldn't change that space.");
    toast(on ? `${space.name} is private now.` : `${space.name} is an ordinary space now.`);
    return true;
  }

  //: The Edit space dialog's Save (bound in spaces-find.js, which hands over its field marker).
  async function save(fail) {
    const id = $("space-edit-id").value;
    const name = $("space-edit-name").value.trim();
    $("space-edit-error").textContent = "";
    $("space-edit-name").removeAttribute("aria-invalid");
    if (!name) return fail("Give the space a name.");
    const was = JSON.parse($("space-edit-dialog").dataset.was || "{}");
    const wantPrivate = $("space-edit-private").checked;
    try {
      const now = { name, icon: $("space-edit-icon").value };
      await apiJson(`/spaces/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(now) });
      pushRequestUndo(`Renamed the space to “${name}”`, `/spaces/${encodeURIComponent(id)}`, "PUT", { name: was.name, icon: was.icon }, now, loadSpaces);
      if (wantPrivate !== was.isPrivate) {
        if (!(await setPrivate({ id, name }, wantPrivate))) return ($("space-edit-private").checked = was.isPrivate);
        reread();
      }
      $("space-edit-dialog").close();
      await loadSpaces();
    } catch (err) {
      fail(err.message);
    }
  }

  //: The Private switch (`label.setting-check`) and the dialog head's '?'
  //: (`data-help-for`), built on the first open rather than shipped in the
  //: page (the boot document's element cap). `prefix` is the dialog's.
  function mount(prefix) {
    if (!$(`${prefix}-private`)) {
      const row = document.createElement("label");
      row.className = "setting-check space-private-row";
      row.htmlFor = `${prefix}-private`;
      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = `${prefix}-private`;
      input.setAttribute("role", "switch");
      const words = document.createElement("span");
      const hint = document.createElement("small");
      hint.className = "muted";
      hint.textContent = "Sealed with your vault password, hidden until you unlock it.";
      words.append("Private ", hint);
      row.append(input, words);
      $(`${prefix}-error`).before(row);
      const head = $(`${prefix}-dialog`).querySelector(".dialog-head");
      const help = document.createElement("button");
      help.type = "button";
      help.className = "icon-only ghost small graph-help-toggle";
      help.setAttribute("data-help-for", `${prefix}-help`);
      help.setAttribute("aria-controls", `${prefix}-help`);
      help.setAttribute("aria-expanded", "false");
      help.title = "What a private space does";
      help.setAttribute("aria-label", help.title);
      const mark = document.createElement("i");
      mark.className = "ph ph-question";
      mark.setAttribute("aria-hidden", "true");
      help.appendChild(mark);
      head.querySelector(".dialog-head-actions").before(help);
      const body = document.createElement("div");
      body.className = "help-body hidden";
      body.id = `${prefix}-help`;
      body.setAttribute("role", "dialog");
      body.setAttribute("aria-label", "What a private space does");
      for (const line of HELP) {
        const p = document.createElement("p");
        p.textContent = line;
        body.appendChild(p);
      }
      head.after(body);
      initHelpToggles(head);
    }
    if (prefix === "space-create") $("space-create-private").checked = false;
  }

  const HELP = [
    "Everything in a private space is sealed with your vault password, as a private note is: notes, documents and boards. It stays out of search, the graph, the timeline, exports and Atlas until you unlock it, and it locks again after the idle minutes in Settings, Account & security, and when the window closes.",
    "Your password opens every private space, and on this computer your PIN or Windows Hello does too. Moving a note out asks whether it stays private.",
  ];

  function edit(id) {
    const { name, icon, is_private: isPrivate } = spacesCache.find((space) => space.id === id);
    mount("space-edit");
    $("space-edit-id").value = id;
    $("space-edit-name").value = name;
    $("space-edit-icon").value = icon;
    $("space-edit-private").checked = Boolean(isPrivate);
    //: The default space is where a deleted space's notes land: never private.
    $("space-edit-private").disabled = id === "default";
    $("space-edit-dialog").dataset.was = JSON.stringify({ name, icon, isPrivate: Boolean(isPrivate) });
    $("space-edit-error").textContent = "";
    spaceIconPicker($("space-edit-icon-picker"), $("space-edit-icon"));
    $("space-edit-dialog").showModal();
    $("space-edit-name").focus();
  }

  //: Always on close: the window going away locks them, whatever the idle clock says.
  window.addEventListener("pagehide", () => {
    api("/private-spaces/lock", { method: "POST", keepalive: true, silent: true, readOnly: true }).catch(backgroundWriteFailed);
  });

  const ACTIONS = { edit, enter, unlock, askKeep, mount, save };
  function privateSpaces(action, ...args) {
    return ACTIONS[action]?.(...args);
  }
  //: hello-unlock.js, the next file in the bundle, adds `hello` here.
  privateSpaces.actions = ACTIONS;

  //: The file's whole surface (ranked row 37a).
  Object.assign(window, { privateSpaces });
})();
