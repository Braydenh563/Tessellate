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

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { unlockPrivateNotes, ensureVaultOpen });
})();
