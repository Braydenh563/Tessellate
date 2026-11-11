// vault-unlock.js: "Unlock private notes" and the guard that asks for it.
// Moved out of app.js on 2026-10-05 (the boot-script gzip budget): both run
// only after a person's click on a private note's chip or a private-note menu
// item, and `askPasswordPrompt`, `settleLockPrompt` and the `lockPrompt`
// state they borrow stay in app.js, where the lock screen needs them at
// boot. `LAZY_MODULES.vault` (app.js) stands in for both until this loads;
// `ensureVaultOpen`'s answer reaches its caller through the stand-in.

//: "Unlock private notes": the vault's key, for a session that started
//: without the password. The token is kept; only the key is loaded.
(() => {
  async function unlockPrivateNotes() {
    const opened = await askPasswordPrompt({
      title: "Unlock private notes",
      message: "Enter your password to read your private notes.",
      submitLabel: "Unlock",
      submit: (password) =>
        apiJson("/auth/unlock-vault", {
          method: "POST",
          body: JSON.stringify({ password }),
          // 401 here is "wrong password", said beside the field.
          ownsAuthErrors: true,
        }),
    });
    if (!opened) return false;
    vaultOpen = true;
    toast("Private notes unlocked.");
    await loadEntries().catch(() => {});
    return true;
  }

  //: True when the vault's key is loaded, asking for the password if not.
  async function ensureVaultOpen() {
    if (vaultOpen === true) return true;
    const info = await apiJson("/auth/account").catch(() => null);
    if (info && info.vault_open) {
      vaultOpen = true;
      return true;
    }
    return unlockPrivateNotes();
  }


  //: **The words typed and not yet saved** (INBOX 1747, row 22, owner 2026-11-11): on a
  //: lock they are sealed on the server (`PUT /kept-words`, the vault key), the fields are
  //: emptied, and the next unlock puts them back. Enumerated like `LOCK_PURGE_IDS`: a privacy
  //: boundary a reviewer reads. Settings and sign-in fields are not here (the app refills them).
  const TYPED_IDS = [
    "entry-title", "entry-content", "entry-tags", "draft-thoughts", "draft-text", "draft-instruction", "draft-tags",
    "question", "capture-bar-input", "quick-note-text", "chat-input", "chat-compress-text", "reminder-magic",
    "reminder-text", "meeting-title", "meeting-transcript", "graph-new-note-title", "graph-new-content",
    "graph-new-tags", "graph-popup-content", "graph-popup-tags", "doc-assist-question", "doc-ai-instruction",
    "doc-ai-result", "doc-replace-find", "doc-replace-with", "ocr-edit-box", "wb-import-text", "help-chat-input",
    "bookmark-url-input", "bookmark-title-input", "bookmark-group-input", "bookmark-note-input", "memory-new",
    "note-search", "ask-history-search", "chat-sidebar-search", "timeline-search", "library-search",
    "library-docs-search", "library-images-search", "bookmark-search", "web-query", "graph-search",
  ];
  //: Typed into a dialog that closes with the lock: emptied, never kept (nothing to come back to).
  const SEARCH_ONLY_IDS = ["command-palette-input", "finder-input", "palette-input", "global-find-input", "note-picker-search"];

  const EDIT_DRAFT = "note-edit-draft";
  const fieldsOf = (ids) => ids.map((id) => document.getElementById(id)).filter((el) => el && el.value);
  const typedFields = () => fieldsOf(TYPED_IDS);

  //: Seal what is typed, then empty it. A refusal (sign-in off: nothing is private) or a failed
  //: request leaves the words where they are: losing a draft is worse than a cover that is not.
  async function keepTypedWords() {
    const found = typedFields();
    const fields = Object.fromEntries(found.map((el) => [el.id, el.value]));
    //: A private note being edited keeps its text in this browser too (`note-edit-draft`, the
    //: edit form's copy): it goes into the same seal and off the page (INBOX 1747, row 26).
    const editing = prefs.get(EDIT_DRAFT, "");
    if (editing) fields[`@${EDIT_DRAFT}`] = editing;
    if (!found.length && !editing) return true;
    try {
      await apiJson("/kept-words", { method: "PUT", body: JSON.stringify({ fields }), silent: true, ownsAuthErrors: true });
    } catch {
      return false;
    }
    for (const el of [...found, ...fieldsOf(SEARCH_ONLY_IDS)]) el.value = "";
    prefs.remove(EDIT_DRAFT);
    if (typeof noteFormDraft !== "undefined") noteFormDraft = null;
    return true;
  }

  //: After an unlock: hand the sealed words back to fields that are still empty (never over
  //: something typed since), tell the fields, and offer the way to pick them up.
  async function restoreTypedWords() {
    const kept = await apiJson("/kept-words", { silent: true }).catch(() => null);
    const entries = Object.entries(kept?.fields || {});
    let back = 0;
    for (const [id, value] of entries) {
      if (id === `@${EDIT_DRAFT}`) {
        //: Back in this browser's store; the edit form offers it beside its note (note-edit-panels.js).
        if (!prefs.has(EDIT_DRAFT)) prefs.set(EDIT_DRAFT, value);
        if (typeof offerKeptNoteEdit === "function") offerKeptNoteEdit();
        continue;
      }
      const el = TYPED_IDS.includes(id) ? document.getElementById(id) : null;
      if (!el || el.value) continue;
      el.value = value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      back += 1;
    }
    if (entries.length) await api("/kept-words", { method: "DELETE", silent: true }).catch(() => {});
    if (back) toast(`Your typed words are back. ${back === 1 ? "One box" : `${back} boxes`} to finish.`, false, { action: ["Where you left off", openLeftOff] });
  }

  //: "Where you left off": a menu of every page box that holds typed words, newest surface
  //: first as the tabs run, each row a jump to its box. Reached from the unlock toast, the
  //: palette and the Guide; the same list at any time, not only after a lock.
  function openLeftOff() {
    const rows = typedFields().filter((el) => el.closest(".tab-page") && !el.closest("[hidden], dialog:not([open])"));
    const items = rows.length
      ? rows.map((el) => {
          const page = el.closest(".tab-page").id.replace("tab-", "");
          const label = el.getAttribute("aria-label") || el.placeholder || el.id;
          const words = el.value.replace(/\s+/g, " ").trim();
          return { label: `ph:pencil-simple ${label}: ${words.length > 48 ? `${words.slice(0, 48)}…` : words}`, run: () => jumpToTyped(el, page) };
        })
      : [{ label: "ph:check Nothing typed and unsaved right now.", run: () => {} }];
    openMenuAtPoint(items, "Where you left off", Math.round(window.innerWidth / 2) - 120, 96);
  }

  async function jumpToTyped(el, page) {
    await switchTab(page);
    //: A box inside a sub-tab (Notes: Capture, Writing room, Ask): show that panel first.
    for (let panel = el.parentElement?.closest('[role="tabpanel"]'); panel; panel = panel.parentElement?.closest('[role="tabpanel"]')) {
      if (panel.classList.contains("hidden") && panel.getAttribute("aria-labelledby")) document.getElementById(panel.getAttribute("aria-labelledby"))?.click();
    }
    el.focus();
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  //: `typedWords` is the one door to the typed-words trio (one name in the shared scope, ranked row 37a).
  const typedWords = (action) => ({ keep: keepTypedWords, restore: restoreTypedWords, open: openLeftOff })[action]();
  Object.assign(window, { unlockPrivateNotes, ensureVaultOpen, typedWords });
})();
