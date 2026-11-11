// sync-folder.js: sync through a folder (WORLD_CLASS_PLAN B6 decision 14, row 36). Lazy (LAZY_MODULES.syncFolder).
//
// Opened from Settings, Import & export, Sync between computers (`#sync-folder-open`). The sheet names a folder on
// this computer (a USB stick, a Syncthing or cloud-drive folder) and a sync passphrase, the same on every computer;
// Sync now reads the other computers' encrypted files there and writes this one's (`POST /sync/folder`,
// entry/folder_sync.py, the home network's apply path). The passphrase is typed each time and never stored.
// Private notes never go into the folder. The result line says what came in; the group's one last-synced line
// follows by the `sync-folder-done` event (settings-rows.js).
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
    if (done.applied) parts.push(`${nounCount(done.applied, "change")} brought in`);
    if (done.conflicts) parts.push(`${nounCount(done.conflicts, "change")} made on both, the other words kept in History`);
    if (done.unreadable) parts.push(`${nounCount(done.unreadable, "file")} could not be opened (check the passphrase)`);
    const wrote = `Wrote ${nounCount(done.shared, "note")}.`;
    const failed = done.error ? ` ${done.error}` : "";
    if (!done.peers && !done.unreadable) return `No other computer has written here yet. ${wrote}`;
    const head = `Read ${nounCount(done.peers, "other computer")}`;
    return `${head}${parts.length ? `: ${parts.join(", ")}` : ", nothing changed"}. ${wrote}${failed}`;
  }

  async function openFolderSync() {
    const last = await apiJson("/sync/folder", { silent: true }).catch(() => ({ folder: "" }));
    openSheet({
      label: "Sync through a folder",
      sub: "Notes, documents, boards and files travel through a folder you choose, encrypted. Private notes stay where they are.",
      name: "sync-folder",
      build: (card) => {
        const folder = document.createElement("input");
        folder.type = "text";
        folder.value = last.folder || "";
        folder.placeholder = "Path to the shared folder";
        folder.setAttribute("aria-label", "Shared folder");
        const phrase = document.getElementById("sync-folder-passphrase").content.firstElementChild.cloneNode(true);
        const status = document.createElement("p");
        status.className = "muted";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
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
          document.dispatchEvent(new CustomEvent("sync-folder-done"));
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
