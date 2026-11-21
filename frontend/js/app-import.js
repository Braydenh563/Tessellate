// Import from another app: Notion, Obsidian, Evernote, Apple Notes and a
// Tessellate notebook folder (WORLD_CLASS_PLAN H6, 5.7, row 25 and 25b).
// Settings, Import & export. Every import keeps a report, opened here
// (`openImportReport`) from the status line, the Activity panel and the
// Background jobs line.
// Loaded when that section opens (settings.js). The readers are
// entry/app_import.py behind `POST /import/app?source=`.
//
// Two steps, the recipe every multi-note import here follows (DESIGN.md,
// "Choosing files to bring in"; INBOX 1520, the owner): each button opens its
// picker, choosing shows the preview (`importPreview`: what will come in,
// every note a tick), and the press that follows runs it. The toast's Undo
// then bins exactly the notes it made (`undoImport`, settings-data.js).
// Importing the same export again makes nothing new: each note remembers
// where it came from, and the preview and the status line say how many were
// already here.

//: **The preview step** (audit 1031 S36). `rows` are `{key, title, snippet,
//: already}`; answers the keys the person left unticked, or null when they
//: closed it. A note already here starts unticked: the run would skip it.
function importPreview({ label, rows, more = 0 }) {
  return new Promise((resolve) => {
    let answered = false;
    const answer = (value) => {
      if (answered) return;
      answered = true;
      resolve(value);
    };
    const boxes = [];
    openSheet({
      label: "Import preview",
      sub: `${nounCount(rows.length + more, "note")} from ${label}. Untick any you do not want.`,
      name: "import-preview",
      onClose: () => answer(null),
      build: (card, close) => {
        card.classList.add("import-report-card");
        const summary = document.createElement("p");
        summary.className = "import-report-counts";
        summary.setAttribute("aria-live", "polite");
        const run = smallButton("ph:check Import", "Bring the ticked notes in", () => {
          answer(rows.filter((row, at) => !boxes[at].checked).map((row) => row.key));
          close();
        }, false);
        run.classList.add("accent");
        const refresh = () => {
          const n = boxes.filter((box) => box.checked).length + more;
          summary.textContent = `${nounCount(n, "note")} will be imported.` + (more ? ` The ${more} past the first ${rows.length} come too.` : "");
          setLabel(run, `ph:check Import ${n}`);
          run.disabled = n === 0;
        };
        const all = (on) => () => {
          boxes.forEach((box) => { box.checked = on; });
          refresh();
        };
        const tools = document.createElement("div");
        tools.className = "row";
        tools.append(
          smallButton("Select all", "Tick every note", all(true)),
          smallButton("Select none", "Untick every note", all(false)),
        );
        const list = document.createElement("ul");
        list.className = "entry-list import-report-list";
        rows.forEach((row) => {
          const li = document.createElement("li");
          const tick = document.createElement("label");
          tick.className = "row align-center checkbox-label small";
          const box = document.createElement("input");
          box.type = "checkbox";
          box.checked = !row.already;
          box.addEventListener("change", refresh);
          boxes.push(box);
          const name = document.createElement("strong");
          name.textContent = row.title || "Untitled";
          tick.append(box, name);
          const detail = document.createElement("p");
          detail.className = "muted task-detail";
          detail.textContent = (row.already ? "Already here. " : "") + (row.snippet || "");
          li.append(tick, detail);
          list.appendChild(li);
        });
        const actions = document.createElement("div");
        actions.className = "row right space-dialog-actions";
        actions.append(smallButton("Cancel", "Import nothing", close), run);
        card.append(summary, tools, list, actions);
        refresh();
      },
    });
  });
}

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
  setLabel(status, `ph:spin Reading ${spec.label}…`);
  let left = [];
  try {
    const seen = await (await api.upload(`/import/app?source=${spec.source}&dry_run=1`, form)).json();
    if (!seen.found) {
      status.textContent = `No ${spec.label} notes in what you chose.`;
      return;
    }
    const chosen = await importPreview({ label: spec.label, rows: seen.notes, more: seen.more });
    if (chosen === null) {
      status.textContent = "Nothing was imported.";
      return;
    }
    left = chosen;
  } catch (error) {
    status.textContent = error.message || `Couldn't read ${spec.label}.`;
    status.classList.add("error");
    return;
  }
  if (left.length) form.append("exclude", JSON.stringify(left));
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
    toastAction(voiceLine("failed", { what: "open the report", why: error.message }), "Try again", () => openImportReport(id));
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
