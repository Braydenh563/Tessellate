// Import from another app: Notion, Obsidian, Evernote, Apple Notes and a
// Tessellate notebook folder (WORLD_CLASS_PLAN H6, 5.7, row 25 and 25b).
// Settings, Import & export. Every import keeps a report, opened here
// (`openImportReport`) from the status line, the Activity panel and the
// Background jobs line.
// Loaded when that section opens (settings.js). The readers are
// entry/app_import.py behind `POST /import/app?source=`.
//
// One step, the recipe every import here follows (DESIGN.md, "Choosing files
// to bring in"): each button opens its picker, choosing starts the import,
// and the toast's Undo bins exactly the notes it made (`undoImport`,
// settings-data.js). Importing the same export again makes nothing new: each
// note remembers where it came from, and the status line says how many were
// already here.

const APP_IMPORTS = [
  { source: "notion", button: "import-notion", input: "import-notion-file", label: "Notion" },
  { source: "obsidian", button: "import-obsidian", input: "import-obsidian-file", label: "Obsidian", keep: /\.(md|markdown|txt)$/i },
  { source: "evernote", button: "import-evernote", input: "import-evernote-file", label: "Evernote" },
  { source: "apple", button: "import-apple", input: "import-apple-file", label: "Apple Notes", keep: /\.(md|markdown|txt|html?)$/i },
  { source: "memorymap", button: "import-memorymap", input: "import-memorymap-file", label: "Tessellate" },
];

async function importFromApp(spec) {
  const input = $(spec.input);
  const status = $("import-app-status");
  //: A folder picker hands over everything in the folder (a vault's
  //: `.obsidian/`, its pictures and PDFs); only the files a reader can use are
  //: sent, as the markdown import does.
  const files = [...input.files].filter((file) => !spec.keep || spec.keep.test(file.webkitRelativePath || file.name));
  input.value = "";
  if (!files.length) {
    $("import-app-status").textContent = `No ${spec.label} notes in what you chose.`;
    return;
  }
  const form = new FormData();
  for (const file of files) form.append("files", file, file.webkitRelativePath || file.name);
  setLabel(status, `ph:spin Importing from ${spec.label}…`);
  try {
    //: `api.upload` throws the server's own words on a refusal; the catch
    //: below shows them.
    const response = await api.upload(`/import/app?source=${spec.source}`, form);
    const body = await response.json().catch(() => ({}));
    const parts = [`Imported ${nounCount(body.imported, "note")} from ${spec.label}.`];
    if (body.already) parts.push(`${body.already} ${body.already === 1 ? "was" : "were"} already here.`);
    if (body.skipped && body.skipped.length) parts.push(`Left out ${body.skipped.length}: ${body.skipped.slice(0, 2).join("; ")}.`);
    if (!body.found) parts.splice(0, parts.length, `No ${spec.label} notes in what you chose.`);
    if (body.stopped) parts.unshift("Stopped part way.");
    status.textContent = parts.join(" ");
    if (body.report) status.append(" ", importReportButton(body.report));
    if (body.ids && body.ids.length && (await ensureModule("settingsData"))) undoImport(body, status);
    refreshEntries(body.ids || []).catch(() => {});
    refreshJobRuns();
  } catch (error) {
    status.textContent = error.message || `Couldn't import from ${spec.label}.`;
    status.classList.add("error");
  }
}

for (const spec of APP_IMPORTS) {
  $(spec.button)?.addEventListener("click", () => {
    $("import-app-status").classList.remove("error");
    $(spec.input).click();
  });
  $(spec.input)?.addEventListener("change", () => importFromApp(spec));
  //: This file loads lazily when the Data pane opens, so a file chosen before
  //: it arrived fired its `change` with no listener and was dropped without a
  //: word. Whatever is already chosen is imported now.
  if ($(spec.input)?.files?.length) importFromApp(spec);
}

// --- The import report (WORLD_CLASS 25b) ------------------------------------
// A sheet (the `openSheet` recipe): the counts, then every file or note left
// out with its reason, then what came in with a caveat. The server keeps the
// last twenty reports, so the page outlives the status line and a restart.

function importReportButton(id) {
  const button = smallButton("ph:file-text See the report", "What this import read, wrote, left out and found already here", () => openImportReport(id));
  button.classList.add("import-report-open");
  return button;
}

function importReportSection(card, heading, items, empty) {
  const title = document.createElement("h3");
  title.textContent = `${heading} (${items.length})`;
  card.appendChild(title);
  if (!items.length) {
    const none = document.createElement("p");
    none.className = "muted";
    none.textContent = empty;
    card.appendChild(none);
    return;
  }
  const list = document.createElement("ul");
  list.className = "entry-list import-report-list";
  for (const item of items) {
    const li = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = item.name || "The import";
    const reason = document.createElement("p");
    reason.className = "muted task-detail";
    reason.textContent = item.reason ? item.reason[0].toUpperCase() + item.reason.slice(1) : "";
    li.append(name, reason);
    list.appendChild(li);
  }
  card.appendChild(list);
}

function importReportCounts(counts) {
  const line = document.createElement("p");
  line.className = "import-report-counts";
  const merged = counts.merged ? `, ${counts.merged} already here` : "";
  line.textContent = `Read ${counts.read}, wrote ${counts.written}, skipped ${counts.skipped}${merged}.`;
  return line;
}

async function openImportReport(id) {
  let report;
  try {
    report = await apiJson(`/import/reports/${encodeURIComponent(id)}`);
  } catch (error) {
    toastAction(`Could not open the report: ${error.message}`, "Try again", () => openImportReport(id));
    return;
  }
  const when = whenText(report.finished_at);
  openSheet({
    label: "Import report",
    sub: `From ${report.label}, ${when}${report.stopped ? ", stopped part way" : ""}.`,
    name: "import-report",
    build: (card) => {
      card.classList.add("import-report-card");
      card.appendChild(importReportCounts(report.counts));
      importReportSection(card, "Skipped", report.skipped, "Nothing was left out.");
      if (report.notes.length) importReportSection(card, "Worth knowing", report.notes, "");
    },
  });
}
window.openImportReport = openImportReport;
