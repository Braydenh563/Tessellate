// settings-data.js: Settings' Privacy record and its Backups and Import
// panes. A lazy piece (app.js LAZY_MODULES), moved out of settings-panes.js on
// 2026-10-03 (INBOX 432) to keep the boot scripts under their gzip total:
// nothing here runs until one of those panes is opened or one of its buttons
// pressed. Their state and their button wiring stay at boot, and reach these
// through LAZY_ENTRY_POINTS.

let privacyReceipt = null;

function privacyWhen(iso) {
  if (!iso) return "";
  return relativeTime(iso);
}

//: **One row per place, saying what it was for** (INBOX 807, the owner: "it
//: isnt really clear exactly what these were for"). A name lookup and the
//: connects to the addresses it returned are one place, grouped under the
//: name a person recognises; the purposes the code named as it reached out
//: ("Downloading the English OCR data", "Web search for 'gaming mouse'")
//: lead, and the raw addresses sit behind the `.task-log` fold.
const PRIVACY_SCOPE_ORDER = ["internet", "local_network", "this_computer"];

function privacyGroups(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = row.name || row.host;
    const group = groups.get(key) || { label: key, rows: [], purposes: [], roles: [], scope: row.scope, last: "" };
    group.rows.push(row);
    for (const words of row.purposes || []) if (!group.purposes.includes(words)) group.purposes.push(words);
    const role = row.role && row.role !== "unattributed" ? row.role : "";
    if (role && !group.roles.includes(role)) group.roles.push(role);
    if (PRIVACY_SCOPE_ORDER.indexOf(row.scope) < PRIVACY_SCOPE_ORDER.indexOf(group.scope)) group.scope = row.scope;
    if (String(row.last || "") > group.last) group.last = String(row.last || "");
    groups.set(key, group);
  }
  return [...groups.values()].sort((a, b) => b.last.localeCompare(a.last));
}

function privacyAddressLine(row) {
  const address = row.port ? `${row.host}:${row.port}` : row.host;
  //: INBOX 894: a device on this network opening the app is a row too,
  //: by its address only; it came in, nothing here reached out to it.
  const verb = row.kind === "lookup" ? "Looked up" : row.kind === "incoming" ? "Came in from" : "Connected to";
  return `${verb} ${address}, ${row.count} time${row.count === 1 ? "" : "s"}, last ${privacyWhen(row.last)}`;
}

function privacyDestinationRow(group) {
  const li = document.createElement("li");
  li.className = "entry-item privacy-row";
  const head = document.createElement("div");
  head.className = "row align-center privacy-row-head";
  const where = document.createElement("span");
  where.className = "privacy-host";
  where.textContent = group.label;
  head.appendChild(where);
  const scope = document.createElement("span");
  scope.className = "chip";
  chipWords(scope, PRIVACY_SCOPE_WORDS[group.scope] || group.scope);
  head.appendChild(scope);
  li.appendChild(head);
  if (group.purposes.length) {
    const why = document.createElement("p");
    why.className = "privacy-row-why";
    why.textContent = `For: ${group.purposes.join("; ")}`;
    li.appendChild(why);
  }
  const connects = group.rows.filter((row) => row.kind !== "lookup");
  const counted = connects.length ? connects : group.rows;
  const count = counted.reduce((sum, row) => sum + (row.count || 0), 0);
  const incoming = connects.length && connects.every((row) => row.kind === "incoming");
  const verb = incoming ? "came in" : connects.length ? "connected" : "looked up";
  const what = group.roles.length ? group.roles.join(", ") : "No feature named";
  const meta = document.createElement("p");
  meta.className = "library-file-meta privacy-row-meta";
  meta.textContent = [
    what.charAt(0).toUpperCase() + what.slice(1),
    `${verb} ${count} time${count === 1 ? "" : "s"}`,
    `last ${privacyWhen(group.last)}`,
  ].join(" · ");
  li.appendChild(meta);
  const fold = document.createElement("details");
  fold.className = "task-log";
  const summary = document.createElement("summary");
  summary.textContent = `Addresses (${group.rows.length})`;
  const pre = document.createElement("pre");
  pre.className = "task-log-lines";
  pre.textContent = group.rows.map(privacyAddressLine).join("\n");
  fold.append(summary, pre);
  li.appendChild(fold);
  return li;
}

function renderPrivacyRange() {
  const receipt = privacyReceipt;
  if (!receipt) return;
  const ledger = privacyRange === "ledger";
  const verdictKey = ledger ? receipt.ledger?.verdict : receipt.verdict;
  const [icon, words, warn] = PRIVACY_VERDICTS[verdictKey] || PRIVACY_VERDICTS.stayed_on_this_computer;
  const verdict = $("privacy-verdict");
  verdict.classList.toggle("notice-warn", warn);
  setLabel(verdict, `${icon} ${words}`);
  //: `.linklike` (DESIGN.md's recipe for a word made clickable in prose):
  //: the status named a record with no way to it (INBOX 431). Jumps to the
  //: list rather than repeating its facts; `privacy-range-note` states
  //: those once already.
  const jump = document.createElement("button");
  jump.type = "button";
  jump.className = "linklike";
  jump.textContent = "See the full list";
  //: `openSettingsModal`'s own deep-link path (this section is already
  //: open, so it only scrolls and rings `flashRevealed`, the same cue
  //: every catalogue row lands with, INBOX 430).
  jump.addEventListener("click", () => openSettingsModal("privacy", "privacy-destinations"));
  verdict.append(" ", jump);
  for (const button of document.querySelectorAll("#privacy-range [data-range]")) {
    const on = button.dataset.range === privacyRange;
    button.setAttribute("aria-pressed", String(on));
    //: `.active` too: the `.seg` recipe draws its chosen segment from the
    //: class (03-dashboard-widgets.css), so with aria-pressed alone neither
    //: looked chosen (the owner, INBOX 430).
    button.classList.toggle("active", on);
  }
  const since = ledger ? receipt.ledger?.since : receipt.watching_since;
  const totals = (ledger ? receipt.ledger?.totals : receipt.totals) || {};
  const local = totals.this_computer || 0;
  $("privacy-range-note").textContent =
    `Since ${since ? whenText(since) : "this launch"}. ` +
    `${local.toLocaleString()} connection${local === 1 ? "" : "s"} stayed on this computer ` +
    "(your model and the app's own window) and are counted, not listed.";
  const all = (ledger ? receipt.ledger?.destinations : receipt.destinations) || [];
  //: A name lookup followed by a connect to the address it returned is one
  //: visit, and the connect row carries the name: `privacyGroups` puts them
  //: in one row, and a lookup that led nowhere still has its own (it is a
  //: question that left the machine).
  const groups = privacyGroups(all);
  const list = $("privacy-destinations");
  list.replaceChildren(...groups.map(privacyDestinationRow));
  $("privacy-empty").classList.toggle("hidden", groups.length > 0);
}

async function renderPrivacyReceipt() {
  const list = $("privacy-destinations");
  const switchRows = $("privacy-switches");
  showSkeletons(list, 2, "li");
  showSkeletons(switchRows, 3, "li");
  let receipt;
  try {
    receipt = await apiJson("/privacy/receipt", { silent: true });
    clearSkeletons(list);
    clearSkeletons(switchRows);
  } catch {
    clearSkeletons(list);
    clearSkeletons(switchRows);
    surfaceFailed($("privacy-empty"), "the privacy record", () => renderPrivacyReceipt());
    $("privacy-empty").classList.remove("hidden");
    list.replaceChildren();
    return;
  }
  surfaceRecovered($("privacy-empty"));
  privacyReceipt = receipt;
  if (receipt.covers) $("privacy-covers").textContent = receipt.covers;
  renderPrivacyRange();

  const model = receipt.model_server || {};
  $("privacy-model").textContent = model.note || "";
  $("privacy-model-meta").textContent = [
    model.url,
    PRIVACY_SCOPE_WORDS[model.scope] || "",
    model.local_only_ai ? "Kept to this computer and your network" : "Hosted models allowed",
  ].filter(Boolean).join(" · ");

  const listening = receipt.listening || {};
  //: A short sentence, then the address block Settings, Other devices draws
  //: (INBOX 867: the run-on list of four addresses was hard to read).
  $("privacy-listening").textContent = listening.other_devices
    ? "Other devices on your network can open it, with your password, at:"
    : listening.held
      ? "Only this computer for now: other devices are kept out on this network."
      : "Only this computer. Nothing on your network can reach it.";
  const where = $("privacy-lan-addresses");
  if (typeof renderLanAddresses === "function") renderLanAddresses(where, listening.other_devices ? listening : {});
  else where?.classList.add("hidden");

  const switches = $("privacy-switches");
  switches.replaceChildren();
  for (const item of receipt.switches || []) {
    //: The Account facts shape: a label column and a value column.
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.className = "account-fact-label";
    name.textContent = item.label;
    const value = document.createElement("span");
    value.textContent = `${item.on ? "On" : "Off"}. ${item.reaches}`;
    li.append(name, value);
    switches.appendChild(li);
  }
}

//: **Where the disk went** (BACKLOG section 26, the owner: "can the user see a
//: visual depiction of the storage size the application takes up"). One bar,
//: a segment per kind as wide as its share, and the same numbers as a legend,
//: which is also the bar's accessible name. `GET /storage` is a cached walk on
//: the server, so opening About costs one request and no tree walk.
const STORAGE_KINDS = [
  ["database_bytes", "Notebook"],
  ["uploads_bytes", "Attached files"],
  ["media_bytes", "Pictures"],
  ["backups_bytes", "Backups"],
  ["extras_bytes", "Optional features"],
];

async function renderStorageBreakdown() {
  const bar = $("storage-bar");
  const legend = $("storage-legend");
  if (!bar || !legend) return;
  lazyScript("/css/settings-data-lazy.css");
  const storage = await apiJson("/storage", { silent: true }).catch(() => null);
  bar.replaceChildren();
  legend.replaceChildren();
  if (!storage) {
    bar.setAttribute("aria-label", "Storage could not be read");
    legend.textContent = "Could not read the sizes.";
    return;
  }
  const kinds = STORAGE_KINDS.map(([key, label]) => ({ key, label, bytes: Number(storage[key]) || 0 }));
  const total = kinds.reduce((sum, kind) => sum + kind.bytes, 0);
  for (const kind of kinds.filter((k) => k.bytes > 0)) {
    const segment = document.createElement("span");
    segment.className = "storage-seg";
    segment.dataset.kind = kind.key;
    segment.style.flexGrow = String(kind.bytes);
    bar.appendChild(segment);
  }
  for (const kind of kinds) {
    const item = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = "storage-swatch";
    swatch.dataset.kind = kind.key;
    swatch.setAttribute("aria-hidden", "true");
    item.append(swatch, `${kind.label} ${humanBytes(kind.bytes)}`);
    legend.appendChild(item);
  }
  const words = `${kinds.map((k) => `${k.label} ${humanBytes(k.bytes)}`).join(", ")}. Together ${humanBytes(total)}.`;
  bar.setAttribute("aria-label", `Storage by kind: ${words}`);
  const sum = document.createElement("li");
  sum.className = "storage-total";
  sum.textContent = `Together ${humanBytes(total)}`;
  legend.appendChild(sum);
}

//: The schedule with its last success (WORLD_CLASS 25e, the Backups row): what
//: the automatic backup is, when it last ran and whether that worked, and when
//: the next is due. The daily rule is the server's (`passes.schedule`,
//: `backup.BACKUP_EVERY_HOURS`), so the words come from `/jobs/last-runs` and
//: the due time is the newest backup plus a day.
function backupScheduleWords(run, newest) {
  const parts = [run?.schedule || "Once a day, at the first start of the day."];
  const day = (iso) =>
    parseServerTime(iso)?.toLocaleString(undefined, { weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit" }) || "";
  if (run?.ran && run.status === "failed") {
    parts.push(`The last try failed${run.error ? `: ${run.error}` : ""}.`);
  } else if (run?.ran && run.finished_at) {
    parts.push(`Last ran ${day(run.finished_at)}${run.status === "ok" ? ", and it worked" : ""}.`);
  } else {
    parts.push("It has not run on this notebook yet.");
  }
  const at = newest ? parseServerTime(newest.created_at) : null;
  if (at) {
    const due = new Date(at.getTime() + 24 * 3600 * 1000);
    parts.push(due.getTime() <= Date.now() ? "Due at the next start." : `Next due ${day(due.toISOString())}, at the first start after that.`);
  }
  return parts.join(" ");
}

async function renderBackupSchedule(backups) {
  const line = $("backup-schedule");
  if (!line) return;
  const runs = await apiJson("/jobs/last-runs", { silent: true }).catch(() => null);
  const run = runs?.jobs?.find((job) => job.kind === "backup");
  line.textContent = backupScheduleWords(run, backups[0]);
}

//: The second place each backup goes (`backup_copy_dir`): a path on the server's
//: own disk, so the row is the desktop app's, like "Save exports to". Saved on
//: blur or Enter; a bad folder is refused with the server's words and the field
//: goes back to what it was.
async function renderBackupCopyRow() {
  const row = $("backup-copy-row");
  if (!row) return;
  const desktop = await desktopShell();
  row.classList.toggle("hidden", !desktop);
  if (!desktop) return;
  const stored = prefsCache || (await apiJson("/preferences", { silent: true }).catch(() => ({})));
  $("pref-backup-copy-dir").value = stored.backup_copy_dir || "";
}

async function saveBackupCopyDir(value) {
  const input = $("pref-backup-copy-dir");
  if (value === (prefsCache?.backup_copy_dir || "")) return;
  try {
    prefsCache = await apiJson("/preferences", { method: "PUT", body: JSON.stringify({ backup_copy_dir: value }) });
    input.value = prefsCache.backup_copy_dir;
    toast(value ? `Each backup is also copied to ${prefsCache.backup_copy_dir}` : "Backups stay on this computer only.");
  } catch (error) {
    input.value = prefsCache?.backup_copy_dir || "";
    toast(error.message || "Couldn't use that folder.", true);
  }
}

$("pref-backup-copy-dir")?.addEventListener("blur", (event) => saveBackupCopyDir(event.target.value.trim()));
$("pref-backup-copy-dir")?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") event.target.blur();
});
$("pref-backup-copy-clear")?.addEventListener("click", () => {
  $("pref-backup-copy-dir").value = "";
  saveBackupCopyDir("");
});

async function renderBackups() {
  const list = $("backup-list");
  renderBackupCopyRow().catch(() => {});
  showSkeletons(list, 2, "li");
  const backups = await apiJson("/backups").catch(() => []);
  clearSkeletons(list);
  list.replaceChildren();
  renderBackupSchedule(backups).catch(() => {});
  for (const item of backups) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "entry-meta";
    //: Which is newest, when in words, what made it, its size and whether it
    //: was checked (INBOX 804 and 805, the owner: "it is unclear which backup
    //: is the latest, and also the backups need more file info").
    const name = document.createElement("strong");
    const at = parseServerTime(item.created_at);
    name.textContent = at
      ? at.toLocaleString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "numeric", minute: "2-digit" })
      : item.name;
    name.title = item.name;
    const size = document.createElement("span");
    size.className = "muted";
    size.textContent = relativeTime(item.created_at);
    const actions = rowActions([
      onOtherDevice() ? null : {
        label: "Restore",
        title: "Roll the notebook back to this backup",
        run: async () => {
          if (
            !(await confirmDialog(
              "Restore this backup? Your current notebook is snapshotted first, " +
                "then replaced by the backup."
            ))
          )
            return;
          try {
            await apiJson("/backups/restore", {
              method: "POST",
              body: JSON.stringify({ name: item.name }),
            });
            toast("Backup restored. Unlock it to carry on.");
            loadEntries().catch(() => {});
            renderBackups();
          } catch (error) {
            toast(error.message, true);
          }
        },
      },
      {
        label: "ph:trash",
        title: "Delete this backup",
        danger: true,
        run: async () => {
          if (!(await confirmDialog("Delete this backup file?"))) return;
          try {
            await apiJson(`/backups/${item.name}`, { method: "DELETE" });
          } catch (error) {
            toast(error.message || "Couldn't delete that backup.", true);
          }
          renderBackups();
        },
      },
    ], "More for this backup");
    if (item.latest) row.append(chip("Latest", "item-label is-yours"));
    row.append(name, size, actions);
    li.appendChild(row);
    //: The facts as badges (INBOX 805): what made it, and whether it was
    //: read back after writing, then the size, any second copy and the file.
    const facts = document.createElement("div");
    facts.className = "entry-meta";
    facts.append(chip(item.origin_words || "Made before backups recorded why", "item-label"));
    facts.append(
      item.checked
        ? chip("ph:check-circle Verified", "item-label is-ok")
        : chip("Not verified", "item-label is-warn")
    );
    const detail = document.createElement("span");
    detail.className = "muted";
    detail.textContent = [
      humanBytes(item.size),
      item.copied_to ? `also copied to ${item.copied_to}` : item.copy_error ? `not copied: ${item.copy_error}` : "",
      item.name,
    ].filter(Boolean).join(" · ");
    facts.append(detail);
    facts.title = item.checked ? "Opened and read back after it was written" : "Not opened and read back";
    li.appendChild(facts);
    list.appendChild(li);
  }
}

// The retention setting itself, separate fetch from renderBackups() (which
// only ever hits GET /backups) because the count/bounds live on GET
// /storage, so this app's own tests that treat GET /backups as a plain list
// of backups don't have to change shape for a control that isn't about any
// one backup.
//: "4.2 MB", for a line a person reads rather than a byte count. The server
//: has the same function (`core/diskspace.human_bytes`), because the notice
//: below is drawn from raw bytes and the toast is built server-side.
function humanBytes(count) {
  if (typeof count !== "number" || !isFinite(count)) return "";
  let size = count;
  for (const unit of ["bytes", "KB", "MB", "GB"]) {
    if (size < 1024 || unit === "GB") {
      return unit === "bytes" ? `${Math.round(size)} bytes` : `${size.toFixed(1)} ${unit}`;
    }
    size /= 1024;
  }
  return "";
}

//: **Say it before a save is the thing that says it** (INBOX 266, item 6).
//: Measured on a data dir filled to 100%: `data_dir_writable` stayed `true`
//: throughout, so the one signal this panel had was a reassurance the app
//: could not keep. The threshold is the server's (`low_space_bytes`), so
//: there is one answer to "is this getting tight" rather than one per
//: screen, and the line names the folder and what is worth deleting rather
//: than only the number.
function renderStorageSpaceNotice(storage) {
  const line = $("storage-space-notice");
  if (!line) return;
  const free = storage && typeof storage.free_bytes === "number" ? storage.free_bytes : null;
  const limit = (storage && storage.low_space_bytes) || 0;
  if (free === null || !limit || free >= limit) {
    line.classList.add("hidden");
    line.replaceChildren();
    return;
  }
  line.classList.remove("hidden");
  setLabel(
    line,
    `ph:warning Only ${humanBytes(free)} left where your notebook is kept ` +
      `(${storage.data_dir}). Deleting old backups below, or exports in ` +
      "Import and export, is usually the quickest space to find."
  );
}

//: The notebook file's check at start (WORLD_CLASS 25e), beside the list
//: that is the way back. Silent when it passed.
function renderIntegrityNotice(check) {
  const line = $("integrity-notice");
  if (!line) return;
  const failed = check && check.ok === false;
  line.classList.toggle("hidden", !failed);
  if (!failed) {
    line.replaceChildren();
    return;
  }
  setLabel(line, `ph:warning ${integrityWords()}`);
}

async function renderBackupRetention() {
  const input = $("backup-retention");
  if (!input) return;
  const storage = await apiJson("/storage", { silent: true }).catch(() => null);
  if (!storage) return;
  renderStorageSpaceNotice(storage);
  renderIntegrityNotice(storage.integrity);
  input.min = storage.backup_retention_min;
  input.max = storage.backup_retention_max;
  input.value = storage.backup_retention_count;
  input.title = `Between ${storage.backup_retention_min} and ${storage.backup_retention_max}`;
}

async function backupNow() {
  const status = $("backup-status");
  try {
    const made = await apiJson("/backups", { method: "POST" });
    status.textContent = `Saved ${made.name}.`;
    renderBackups();
  } catch (error) {
    status.textContent = error.message;
  }
}

async function importDirectory() {
  const pathInput = $("import-dir-path").value.trim();
  const status = $("import-dir-status");
  if (!pathInput) {
    status.textContent = "Please enter a directory path.";
    return;
  }
  setLabel(status, "ph:spin Starting import…");
  try {
    const response = await apiJson("/import/directory", {
      method: "POST",
      body: { path: pathInput },
    });
    status.textContent = "Import started in the background. Check your library soon.";
    $("import-dir-path").value = "";
  } catch (error) {
    status.textContent = error.message;
  }
}

//: The way back from a one-step import (INBOX 464 (18)): choosing the files
//: starts it, so the toast offers Undo, which moves exactly the notes it made
//: (the ids both endpoints return) to the recycle bin, restorable from there.
function undoImport(result, status) {
  const ids = result.ids || [];
  if (!ids.length) return;
  const n = ids.length;
  //: Eight at a time, each settled on its own, so one note already gone does
  //: not stop the rest; answers how many went.
  const each = async (send) => {
    let done = 0;
    for (let at = 0; at < ids.length; at += 8) {
      const settled = await Promise.allSettled(ids.slice(at, at + 8).map(send));
      done += settled.filter((s) => s.status === "fulfilled").length;
    }
    loadEntries().catch(() => {});
    return done;
  };
  //: Rule 1.8: the import is one entry on the undo stack (the bar, Ctrl+Z,
  //: the history menu) and the toast's Undo is that entry. Undo bins exactly
  //: the notes it made; redo takes them back out of the bin.
  const binThem = async () => {
    const binned = await each((id) => apiJson(`/entries/${id}`, { method: "DELETE", silent: true }));
    if (status) status.textContent = `Undone: ${binned} imported note${binned === 1 ? "" : "s"} moved to the bin.`;
  };
  const restoreThem = async () => {
    const back = await each((id) => apiJson(`/entries/${id}/restore`, { method: "POST", silent: true }));
    if (status) status.textContent = `Imported ${back} note${back === 1 ? "" : "s"} again.`;
  };
  offerUndo(`Imported ${n} note${n === 1 ? "" : "s"}`, `Imported ${n} note${n === 1 ? "" : "s"}.`, binThem, restoreThem);
}

async function importMarkdown(inputId = "import-md-files") {
  const input = $(inputId);
  const status = $("import-md-status");
  if (!input.files.length) {
    status.textContent =
      inputId === "import-md-folder"
        ? "Choose a folder first."
        : "Choose one or more .md files first.";
    return;
  }
  const form = new FormData();
  //: The third argument is the filename the server sees, and `webkitRelativePath`
  //: is the only place a folder picker puts the path, `file.name` is the bare
  //: name even when the file came from three folders down. Sending the path is
  //: what lets an imported vault keep its tree (`Entry.source_path`) and its
  //: `[[wiki links]]`, which name the file rather than its opening words.
  //: A vault folder holds far more than markdown (`.obsidian/`, images,
  //: PDFs), and the picker hands over every one of them, filtering here
  //: keeps the request from being mostly files the endpoint would reject one
  //: at a time and report as "skipped".
  const chosen = [...input.files].filter((file) =>
    /\.(md|markdown|txt)$/i.test(file.webkitRelativePath || file.name),
  );
  if (!chosen.length) {
    status.textContent = "No markdown files in that folder.";
    return;
  }
  for (const file of chosen) {
    form.append("files", file, file.webkitRelativePath || file.name);
  }
  input.value = "";
  setLabel(status, `ph:spin Importing ${chosen.length} file${chosen.length === 1 ? "" : "s"}…`);
  try {
    // `api.upload` (F5): the multipart type from the browser, and
    // X-Workspace-ID, without which the notes land in the default space.
    const response = await api.upload("/import/markdown", form).catch(() => {
      throw new Error("The import did not work. Check the file and try again.");
    });
    const result = await response.json();
    status.textContent =
      `Imported ${result.imported} note${result.imported === 1 ? "" : "s"}.` +
      //: Passed over because the same file and text are already a note.
      (result.already ? ` ${result.already} already in your notebook, left as they are.` : "") +
      (result.skipped.length ? ` Skipped: ${result.skipped.join("; ")}` : "");
    undoImport(result, status);
    loadEntries().catch(() => {});
  } catch (error) {
    status.textContent = error.message;
  }
}

// §37G: a document (PDF/Word/slide deck) becomes one or more notes, via the
// markitdown extra: the same "Import" pattern as importMarkdown above, one
// file at a time rather than several, since a document commonly becomes
// several notes on its own (one per chapter or slide).
async function importDocument() {
  const input = $("import-document-file");
  const status = $("import-document-status");
  const file = input.files[0];
  if (!file) {
    status.textContent = "Choose a file first.";
    return;
  }
  const form = new FormData();
  form.append("file", file);
  input.value = "";
  setLabel(status, `ph:spin Importing ${file.name}…`);
  try {
    const response = await api.upload("/import/document", form);
    const result = await response.json();
    status.textContent =
      `Imported ${result.imported} note${result.imported === 1 ? "" : "s"}` +
      ` from ${result.filename}.` +
      (result.truncated ? " (Stopped at the note limit, the rest wasn't imported.)" : "");
    undoImport(result, status);
    loadEntries().catch(() => {});
  } catch (error) {
    status.textContent = error.message;
  }
}

// Moved from settings-panes.js (boot gzip): every caller is in this file.
const PRIVACY_VERDICTS = {
  stayed_on_this_computer: ["ph:shield-check", "Nothing left this computer.", false],
  local_network: ["ph:wifi-high", "Only devices on your own network were contacted.", false],
  internet: ["ph:globe-hemisphere-west", "This app connected to the internet. Each connection is listed below.", true],
};

// Moved from settings-panes.js (boot gzip): every caller is in this file.
const PRIVACY_SCOPE_WORDS = {
  this_computer: "This computer",
  local_network: "Your network",
  internet: "The internet",
};

// --- Settings, Data: "Clear and forget" (Brief 86, decision b) ---------------
//
// The owner, 2026-10-11: "should the user be able to clear their cache and
// recent searches in individual and all places and clear other things". Four
// rows, each saying what it removes and how much, each undoable from its toast
// for ten seconds (rule 1.8: `offerUndo`):
//
// - Recent searches, everywhere: every box's list (prefs.js `searchRecent`).
// - Cached previews and thumbnails: the pictures, attachment facts and map
//   previews this window holds (no file on disk: they are drawn again when
//   needed, so that clear has nothing to put back).
// - The Guide's conversation: what was asked in this window (the Guide keeps
//   no answer cache; its memory is this transcript).
// - Dismissed suggestions: what the person said no to (merges, link types,
//   links, contradictions, resurfaced notes, insights); the server marks them
//   forgotten and can mark them remembered again (`/suggestions/dismissed`).
//
// Lives here, in the Data pane's own lazy piece: app.js is at its gzip cap, and the
// pane that opens this file is the one that shows these rows.

function settingsClearCount(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

//: The caches that hold a picture or a preview, by name, with what they hold.
//: Each is a Map in the file that fills it; one not loaded yet holds nothing.
function previewCaches() {
  const maps = [];
  if (typeof thumbUrlCache !== "undefined") maps.push(thumbUrlCache);
  if (typeof attachmentMetaCache !== "undefined") maps.push(attachmentMetaCache);
  if (typeof referenceCountsCache !== "undefined") maps.push(referenceCountsCache);
  if (typeof _apiCache !== "undefined") maps.push(_apiCache);
  return maps;
}

function previewCount() {
  const board = typeof mapBoardIndexCache !== "undefined" && mapBoardIndexCache ? mapBoardIndexCache.size : 0;
  return previewCaches().reduce((sum, map) => sum + map.size, 0) + board;
}

function clearPreviews() {
  for (const map of previewCaches()) map.clear();
  if (typeof mapBoardIndexCache !== "undefined") mapBoardIndexCache = null;
}

//: What is in the Guide's transcript: [{role, content}], or [] while it is not loaded.
function guideTurns() {
  return typeof helpChatHistory !== "undefined" && Array.isArray(helpChatHistory) ? helpChatHistory : [];
}

//: Paint one row's sentence and switch its button off when there is nothing to clear.
function paintClearRow(whatId, buttonId, words, count) {
  const what = $(whatId);
  if (what) what.textContent = words;
  const button = $(buttonId);
  if (button) button.disabled = count === 0;
}

async function renderSettingsClear() {
  await ensureModule("searchSuggest");
  const recents = searchRecentAll();
  const total = Object.values(recents).reduce((sum, list) => sum + list.length, 0);
  paintClearRow(
    "clear-recents-what",
    "clear-recents",
    total
      ? `${settingsClearCount(total, "recent search", "recent searches")} in ${settingsClearCount(Object.keys(recents).length, "search box", "search boxes")}, kept on this device.`
      : "No search box has anything remembered.",
    total
  );
  const previews = previewCount();
  paintClearRow(
    "clear-previews-what",
    "clear-previews",
    previews
      ? `${settingsClearCount(previews, "preview", "previews")} held in this window. They are drawn again when needed, so there is nothing to undo.`
      : "Nothing is held right now. Pictures and map previews are kept here while you browse.",
    previews
  );
  const turns = Math.ceil(guideTurns().length / 2);
  paintClearRow(
    "clear-guide-what",
    "clear-guide",
    turns ? `${settingsClearCount(turns, "question", "questions")} in the Guide's conversation, kept in this window only.` : "The Guide's conversation is empty.",
    turns
  );
  const dismissed = await apiJson("/suggestions/dismissed", { silent: true }).catch(() => null);
  const count = dismissed ? dismissed.total : 0;
  const parts = dismissed ? dismissedWords(dismissed) : "";
  paintClearRow(
    "clear-dismissed-what",
    "clear-dismissed",
    count ? `${settingsClearCount(count, "suggestion", "suggestions")} you said no to${parts ? `: ${parts}` : ""}. Clearing lets the app offer them again.` : "You have not dismissed any suggestion.",
    count
  );
}

const DISMISSED_KIND_WORDS = {
  dismiss_merge: ["name merge", "name merges"],
  dismiss_link_type: ["link type", "link types"],
  dismiss_link: ["link", "links"],
  dismiss_tension: ["contradiction", "contradictions"],
  dismiss_resurface: ["old note", "old notes"],
  dismiss_insight: ["insight", "insights"],
};

function dismissedWords(dismissed) {
  const parts = Object.entries(dismissed.by_kind || {}).map(([kind, n]) => {
    const [one, many] = DISMISSED_KIND_WORDS[kind] || [kind, kind];
    return settingsClearCount(n, one, many);
  });
  if (dismissed.tension_pairs) parts.push(settingsClearCount(dismissed.tension_pairs, "contradiction pair", "contradiction pairs"));
  if (dismissed.note_tags) parts.push(settingsClearCount(dismissed.note_tags, "tag turned down on a note", "tags turned down on notes"));
  return parts.join(", ");
}

//: **A clear is a change that can be taken back** (decision c): it is kept in
//: Recent changes with what it removed (`settingsHistoryAdd`), and its toast's
//: Undo is that same entry's, so the toast, the list and the status bar's Undo
//: agree. `data` is what the way back needs, small enough to keep.
function settingsClearDone(change, message) {
  change.at = Date.now();
  change.sig = `${change.kind}:${change.words}`;
  change.label = change.words;
  settingsHistoryAdd(change);
  offerUndo(
    change.words,
    message,
    async () => { await settingsHistoryApply(change, "old"); renderSettingsClear(); },
    async () => { await settingsHistoryApply(change, "new"); renderSettingsClear(); },
    { ms: 10000 }
  );
  if (settingsModalOpen()) renderSettingsClear();
}

$("clear-recents")?.addEventListener("click", async () => {
  await ensureModule("searchSuggest");
  const before = searchRecentClearAll();
  const total = Object.values(before).reduce((sum, list) => sum + list.length, 0);
  if (!total) return;
  //: The web panel draws its list from the store: it repaints.
  renderWebSearchHistory();
  settingsClearDone(
    { kind: "recents", changes: [], words: "Cleared recent searches", data: { before } },
    `Cleared ${settingsClearCount(total, "recent search", "recent searches")}.`
  );
});

$("clear-previews")?.addEventListener("click", () => {
  const count = previewCount();
  if (!count) return;
  clearPreviews();
  toast(`Cleared ${settingsClearCount(count, "preview", "previews")}. They are drawn again when needed.`);
  renderSettingsClear();
});

$("clear-guide")?.addEventListener("click", async () => {
  const turns = guideTurns().slice();
  if (!turns.length) return;
  await ensureModule("helpChat");
  helpChatNewChat();
  settingsClearDone(
    { kind: "guide", changes: [], words: "Cleared the Guide's conversation", data: { turns } },
    `Cleared the Guide's conversation (${settingsClearCount(Math.ceil(turns.length / 2), "question", "questions")}).`
  );
});

//: The words come back; the badges and sources under an answer do not.
function restoreGuideTurns(turns) {
  helpChatNewChat();
  helpChatHistory = turns.slice();
  const empty = $("help-chat-empty");
  if (empty) empty.hidden = true;
  $("help-chat-starters")?.classList.add("hidden");
  for (const turn of turns) renderHelpChatMessage(turn.role, turn.content, [], [], null);
}

$("clear-dismissed")?.addEventListener("click", async () => {
  try {
    const done = await apiJson("/suggestions/dismissed/clear", { method: "POST" });
    if (!done.cleared) return;
    settingsClearDone(
      { kind: "dismissed", changes: [], words: "Cleared dismissed suggestions", data: { ids: done.ids, tensions: done.tensions, note_tags: done.note_tags } },
      `Cleared ${settingsClearCount(done.cleared, "dismissed suggestion", "dismissed suggestions")}: they can be offered again.`
    );
  } catch (error) {
    toast(error.message || "Couldn't clear the dismissed suggestions.", true);
  }
});


// --- Settings, Data: "Recent changes" (Brief 86, decision c) -------------------
//
// Every Settings change and clear is kept with its way back (the owner,
// 2026-10-11: "undo thing in settings??"). What is kept: the last twenty
// (`SETTINGS_HISTORY_MAX`), newest first, on this device, each `{id, at, kind,
// label, changes, data, undone}`. The eager half is status.js
// (`noteSettingChange` and the two choke points that call it: every
// `/preferences` answer, and every look key in ai-tools.js), because it has to
// see a change the moment it is made; this half keeps the list, paints it, and
// applies an Undo or a Redo.
//
// Kinds: "prefs" (the notebook's settings, PUT /preferences), "look" (a
// browser-side appearance key, mirrored to the notebook by ai-tools.js),
// "recents" (the search boxes' remembered searches), "dismissed" (suggestions
// said no to), "guide" (the Guide's transcript). A change that cannot be
// reversed (a value that was never set, a size the list will not hold) is
// listed without a button and says so.

//: Not a change the person made (a mirrored copy, a counter), or not one to keep.
const SETTINGS_HISTORY_SKIP = new Set(["ui_state", "settings_history"]);
const SETTINGS_HISTORY_SECRET = /key|token|secret|password|salt|hash/i;

//: A value as a person reads it, short: on/off for a switch, the words for text.
function settingShown(value) {
  if (value === true || value === "on") return "on";
  if (value === false || value === "off") return "off";
  if (value == null) return "default";
  if (value === "") return "empty";
  if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? "" : "s"}`;
  if (typeof value === "object") return "changed";
  const text = String(value);
  return text.length > 24 ? `${text.slice(0, 23)}…` : text;
}

function settingName(key) {
  const words = String(key).replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function settingChangeWords(change) {
  if (change.words) return change.words;
  const [first] = change.changes;
  const more = change.changes.length > 1 ? ` and ${change.changes.length - 1} more` : "";
  return `${settingName(first.key)}: ${settingShown(first.old)} to ${settingShown(first.new)}${more}`;
}

//: A `/preferences` PUT, diffed against the answer before it (status.js hands
//: both over), so a form that saves twelve fields records the one that changed.
//: The look settings are browser-side (localStorage) and reach the notebook as
//: the `ui_state` copy, a moment after the change (ai-tools.js `saveUiState`):
//: its look keys are diffed one by one, each a change of its own.
function settingsPrefsSeen(before, data) {
  const changes = [];
  for (const key of Object.keys(data)) {
    if (SETTINGS_HISTORY_SKIP.has(key) || SETTINGS_HISTORY_SECRET.test(key)) continue;
    if (JSON.stringify(data[key]) === JSON.stringify(before[key])) continue;
    changes.push({ key, old: before[key], new: data[key] });
  }
  if (changes.length) noteSettingChange({ kind: "prefs", changes });
  const was = before.ui_state || {};
  const now = data.ui_state || {};
  const looks = [...new Set([...Object.keys(was), ...Object.keys(now)])]
    .filter((key) => (LOOK_KEYS.includes(key) || key === "themePreset") && was[key] !== now[key])
    .map((key) => ({ key, old: was[key] ?? null, new: now[key] ?? null }));
  if (looks.length) noteSettingChange({ kind: "look", changes: looks });
}

//: The change a coalescing tick continues, and the toast that will offer its Undo.
const settingFresh = { last: null };

//: `change`: {kind, changes: [{key, old, new}], ...}; `words` overrides the
//: line; `quiet` keeps it off the toast (the caller raised its own Undo).
function noteSettingChange(change, { quiet = false } = {}) {
  change.at = Date.now();
  change.sig = `${change.kind}:${change.words || ""}:${change.changes.map((c) => c.key).sort().join(",")}`;
  //: A slider or a typed field is one change, however many ticks: the first
  //: value it had stays the way back.
  const last = settingFresh.last;
  if (last && last.change.sig === change.sig && change.at - last.change.at < 2500) {
    change.changes.forEach((c, i) => {
      const before = last.change.changes.find((p) => p.key === c.key);
      if (before) change.changes[i] = { ...c, old: before.old };
    });
    clearTimeout(last.timer);
  }
  change.label = settingChangeWords(change);
  settingFresh.last = { change, timer: 0 };
  settingsHistoryAdd(change);
  if (quiet) return;
  //: One notice, with the Undo and long enough to use: the toast the control
  //: raised for its own change (a "Saved", found by its enter animation still
  //: running) makes way for this one, which waits for it.
  settingFresh.last.timer = setTimeout(() => {
    for (const note of toastHost().querySelectorAll(".toast:not(.error)")) {
      if (note.getAnimations().some((a) => a.currentTime < 700)) note.remove();
    }
    toastAction(change.label, "Undo", () => settingsHistoryUndo(change), { ms: 10000, record: false });
  }, 600);
}

//: Every box's remembered searches at once (prefs.js keeps one list per scope).
function searchRecentAll() {
  const found = {};
  const store = prefsStore();
  for (let i = 0; store && i < store.length; i++) {
    const name = store.key(i) || "";
    const scope = name === "webSearchHistory" ? "web" : name.startsWith(SEARCH_RECENT_PREFIX) ? name.slice(SEARCH_RECENT_PREFIX.length) : "";
    const list = scope ? searchRecent.load(scope) : [];
    if (list.length) found[scope] = list;
  }
  return found;
}

function searchRecentClearAll() {
  const before = searchRecentAll();
  for (const scope of Object.keys(before)) searchRecent.clear(scope);
  return before;
}

function searchRecentRestore(before) {
  for (const [scope, list] of Object.entries(before || {})) prefs.setJSON(searchRecent.key(scope), list);
}

const SETTINGS_HISTORY_KEY = "settingsHistory";
const SETTINGS_HISTORY_MAX = 20;
//: The largest stored entry; past it the way back is dropped and the row says so.
const SETTINGS_HISTORY_ENTRY_BYTES = 12000;

const settingsHistoryBigKept = new Map();

function settingsHistoryLoad() {
  return prefs.json(SETTINGS_HISTORY_KEY, []).filter((entry) => entry && typeof entry === "object" && entry.id);
}

function settingsHistorySave(list) {
  prefs.setJSON(SETTINGS_HISTORY_KEY, list.slice(0, SETTINGS_HISTORY_MAX));
}

//: The entry as it is kept: a way back that was never known or is too big is
//: dropped, and the row says "Can't be undone" rather than offering a button
//: that would fail.
function settingsHistoryEntry(change) {
  const entry = { ...change, id: change.id || `${change.at}-${Math.random().toString(36).slice(2, 6)}` };
  //: A setting that was never set has no old value to send back: Undo asks the
  //: notebook to unset it (`unset` on PUT /preferences), so every row can undo.
  if (entry.kind === "prefs") entry.changes = (entry.changes || []).map((c) => (c.old === undefined ? { ...c, old: null, unset: true } : c));
  const big = JSON.stringify(entry).length > SETTINGS_HISTORY_ENTRY_BYTES;
  if (big) {
    //: Too big for the browser's store: the way back is held in memory, so it
    //: undoes until the page reloads, and the row says so after that.
    settingsHistoryBigKept.set(entry.id, { changes: entry.changes, data: entry.data });
    entry.big = true;
    entry.changes = (entry.changes || []).map((c) => ({ key: c.key }));
    entry.data = null;
  }
  change.id = entry.id;
  return entry;
}

//: Called by status.js `noteSettingChange` once this file is here.
function settingsHistoryAdd(change) {
  const list = settingsHistoryLoad();
  const entry = settingsHistoryEntry(change);
  //: A slider's ticks are one change (status.js carried the first old value
  //: forward): this replaces the entry the last tick made.
  if (list[0] && list[0].sig === entry.sig && entry.at - list[0].at < 2500) list.shift();
  list.unshift(entry);
  settingsHistorySave(list);
  renderSettingsHistory();
}

function settingsHistoryFind(change) {
  return settingsHistoryLoad().find((entry) => entry.id === change.id) || null;
}

//: Reapply one side of a change: "old" is Undo, "new" is Redo.
async function settingsHistoryApply(change, side) {
  const kept = settingsHistoryFind(change) || change;
  const held = kept.big ? settingsHistoryBigKept.get(kept.id) : null;
  if (held) Object.assign(kept, held);
  if (kept.noUndo || change.noUndo || (kept.big && !held)) throw new Error("That change can't be undone: its old value was not kept.");
  settingsHistoryBusy = true;
  try {
    if (kept.kind === "prefs") {
      const body = {};
      const unset = [];
      for (const c of kept.changes) {
        if (side === "old" && c.unset) unset.push(c.key);
        else body[c.key] = c[side];
      }
      if (unset.length) body.unset = unset;
      prefsCache = await apiJson("/preferences", { method: "PUT", body: JSON.stringify(body) });
    } else if (kept.kind === "look") {
      for (const c of kept.changes) {
        if (c[side] == null) prefs.remove(c.key);
        else prefs.set(c.key, c[side]);
      }
      //: The path a fresh load applies the look by (the saved themes' own Apply).
      applyThemeChoice(prefs.get("theme", "system"), false);
      applyAppearance();
      if (bgArtOn()) startBgArt();
      else stopBgArt();
      renderAppearance();
    } else if (kept.kind === "recents") {
      await ensureModule("searchSuggest");
      if (side === "old") searchRecentRestore(kept.data.before);
      else for (const scope of Object.keys(kept.data.before)) searchRecent.clear(scope);
      renderWebSearchHistory();
      renderWebPanelMenu(webEngineInfo);
    } else if (kept.kind === "dismissed") {
      if (side === "old") await apiJson("/suggestions/dismissed/restore", { method: "POST", body: JSON.stringify(kept.data) });
      else kept.data = await apiJson("/suggestions/dismissed/clear", { method: "POST" });
    } else if (kept.kind === "guide") {
      await ensureModule("helpChat");
      if (side === "old") restoreGuideTurns(kept.data.turns);
      else helpChatNewChat();
    }
  } finally {
    //: A look is mirrored to the notebook 800 ms after it is written: that PUT
    //: is this Undo's own, not a new change.
    if (kept.kind === "look") setTimeout(() => (settingsHistoryBusy = false), 2500);
    else settingsHistoryBusy = false;
  }
  kept.undone = side === "old";
  if (held) {
    settingsHistoryBigKept.set(kept.id, { changes: kept.changes, data: kept.data });
    kept.changes = kept.changes.map((c) => ({ key: c.key }));
    kept.data = null;
  }
  const list = settingsHistoryLoad().map((entry) => (entry.id === kept.id ? kept : entry));
  settingsHistorySave(list);
  change.undone = kept.undone;
  renderSettingsHistory();
  //: The pane in front shows the value that is now true.
  if (settingsModalOpen()) showSettingsSection(currentSettingsSection);
}

async function settingsHistoryUndo(change) {
  try {
    await settingsHistoryApply(change, "old");
    //: Through the one undo contract (status.js, rule 1.8): an undone change
    //: waits on the redo side, so Redo and Ctrl+Y reach it like any other.
    const action = pushUndo(change.label, () => settingsHistoryApply(change, "old"), () => settingsHistoryApply(change, "new"));
    action.settingChange = change;
    settleUndoFromToast(action);
    toast(`Undone: ${change.label}`);
  } catch (error) {
    toast(error.message || "Couldn't undo that.", true);
  }
}

async function settingsHistoryRedo(change) {
  try {
    await settingsHistoryApply(change, "new");
    //: Done again here, so the redo that waited for it (above) is spent.
    const waiting = redoStack.findIndex((action) => action.settingChange === change);
    if (waiting !== -1) redoStack.splice(waiting, 1);
    renderUndoBar();
    toast(`Done again: ${change.label}`);
  } catch (error) {
    toast(error.message || "Couldn't do that again.", true);
  }
}

function settingsHistoryRow(entry) {
  const li = document.createElement("li");
  li.className = "entry-item recent-change";
  if (entry.undone) li.classList.add("is-undone");
  const words = document.createElement("div");
  words.className = "recent-change-words";
  const label = document.createElement("span");
  label.className = "recent-change-label";
  label.textContent = entry.label;
  const when = document.createElement("small");
  when.className = "muted";
  const ago = relativeTime(new Date(entry.at).toISOString());
  const gone = entry.noUndo || (entry.big && !settingsHistoryBigKept.has(entry.id));
  when.textContent = entry.undone ? `${ago} · undone` : gone ? `${ago} · can't be undone` : ago;
  words.append(label, when);
  li.appendChild(words);
  if (!gone) {
    //: The row-actions recipe (DESIGN.md): a quiet text action, not a bordered
    //: tonal button (INBOX 848).
    const again = entry.undone;
    li.appendChild(
      rowActions(
        [{
          label: again ? "Do again" : "Undo",
          title: again ? `Make this change again: ${entry.label}` : `Put it back: ${entry.label}`,
          run: () => (again ? settingsHistoryRedo(entry) : settingsHistoryUndo(entry)),
        }],
        `Actions for ${entry.label}`
      )
    );
  }
  return li;
}

function renderSettingsHistory() {
  const list = $("recent-changes-list");
  if (!list) return;
  const entries = settingsHistoryLoad();
  if (!entries.length) {
    const none = document.createElement("li");
    none.className = "muted recent-change-empty";
    none.textContent = "Nothing changed yet. Changes you make in Settings appear here.";
    list.replaceChildren(none);
    return;
  }
  list.replaceChildren(...entries.map(settingsHistoryRow));
}
