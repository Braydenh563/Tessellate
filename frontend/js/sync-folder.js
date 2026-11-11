// sync-folder.js: sync without a server (WORLD_CLASS_PLAN row 36, Q34). Lazy (LAZY_MODULES.syncFolder in lazy-entries.js).
//
// The sheet names a folder on this computer (a USB stick, a Syncthing or cloud-drive folder) and a sync passphrase,
// the same on every computer; Sync now reads the other computers' encrypted files there and writes this one's
// (`POST /sync/folder`, entry/folder_sync.py). The passphrase is typed each time and never stored. Private notes
// never go into the folder. When both computers changed the same note the later edit wins and the other words
// stay in the note's History; the result line says how many.
(() => {
  function field(labelText, control) {
    const label = document.createElement("label");
    label.className = "row space-between setting-row";
    const word = document.createElement("span");
    word.textContent = labelText;
    label.append(word, control);
    return label;
  }

  function summary(done) {
    const parts = [];
    if (done.added) parts.push(`${done.added} new`);
    if (done.updated) parts.push(`${done.updated} updated`);
    if (done.conflicts) parts.push(`${done.conflicts} edited on both, both versions kept in History`);
    if (done.unreadable) parts.push(`${done.unreadable} file${done.unreadable === 1 ? "" : "s"} could not be opened (check the passphrase)`);
    const wrote = `Wrote ${done.shared} note${done.shared === 1 ? "" : "s"}.`;
    if (!done.peers && !done.unreadable) return `No other computer has written here yet. ${wrote}`;
    const head = `Read ${done.peers} other computer${done.peers === 1 ? "" : "s"}`;
    return `${head}${parts.length ? `: ${parts.join(", ")}` : ", nothing changed"}. ${wrote}`;
  }

  async function openFolderSync() {
    const last = await apiJson("/sync/folder", { silent: true }).catch(() => ({ folder: "", last: "" }));
    openSheet({
      label: "Sync between computers",
      sub: "Notes travel through a folder you choose, encrypted. Private notes stay where they are.",
      name: "sync-folder",
      build: (card) => {
        const folder = document.createElement("input");
        folder.type = "text";
        folder.value = last.folder || "";
        folder.placeholder = "Path to the shared folder";
        folder.setAttribute("aria-label", "Shared folder");
        const phrase = document.createElement("input");
        phrase.type = "password";
        phrase.autocomplete = "off";
        phrase.placeholder = "The same on every computer";
        phrase.setAttribute("aria-label", "Sync passphrase");
        const status = document.createElement("p");
        status.className = "muted";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        if (last.last) status.textContent = `Last synced ${parseServerTime(last.last).toLocaleString()}.`;
        const go = smallButton("ph:arrows-clockwise Sync now", "Read the other computers' files in the folder and write this one's", async () => {
          go.disabled = true;
          status.textContent = "Syncing";
          try {
            status.textContent = summary(
              await apiJson("/sync/folder", { method: "POST", body: JSON.stringify({ folder: folder.value.trim(), passphrase: phrase.value }) }),
            );
          } catch (error) {
            status.textContent = error.message;
          }
          go.disabled = false;
        }, false);
        const actions = document.createElement("div");
        actions.className = "row";
        actions.append(go);
        card.append(field("Folder", folder), field("Passphrase", phrase), actions, status);
        folder.focus();
      },
    });
  }

  //: The file's whole surface: what the palette and the Tools and features list call (ranked row 37a).
  Object.assign(window, { openFolderSync });
})();
