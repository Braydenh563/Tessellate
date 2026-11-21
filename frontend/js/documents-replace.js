// documents-replace.js: Replace in every document (split out of documents.js,
// audit 1031 DC13).
//
// What is here: the dialog behind the dock menu's "Replace in every document"
// and the command palette's row for it: the pattern, the scan of every
// document's text, the list with a box per document, the two-press Replace
// all, and the writes (`docWriteContents`) that the one undo step also uses.
// It is one concern with one dialog (`#doc-replace-dialog`) and nothing else
// in the editor reads its state.
//
// **Loaded on the first press**, by `openDocReplace` in documents.js (the
// way documents-word.js is): the dialog is rarely opened, so its code is not
// fetched with the editor. Its top level wires the dialog's own controls,
// which exist in index.html by then, and calls nothing from documents.js
// until a function here runs (`saveDocument`, `docCmView`, `currentDoc`).

// --- Replace in every document (DOCUMENTS 24 row 9) ---------------------------
//
// VS Code's replace across files: a pattern (plain or a regular expression,
// matched with or without case), the documents it would change and how many
// times, then Replace all. The texts are rebuilt here and written in one
// request (`POST /documents/contents`), and the one undo step writes the
// originals back the same way, so fifty documents change, or change back,
// whole. Each changed document keeps the version it replaced in its history.
const docReplace = { matches: [], skipped: new Set(), timer: 0, late: 0, pool: null };

function docReplacePattern() {
  const find = $("doc-replace-find").value;
  if (!find) return null;
  const flags = $("doc-replace-case").checked ? "g" : "gi";
  const regex = $("doc-replace-regex").checked;
  const source = regex ? find : find.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  //: Whole word by letters in any script, not `\b`, which ends a word at "é" (D29).
  const word = $("doc-replace-word").checked;
  const wrapped = word ? `(?<![\\p{L}\\p{N}_])(?:${source})(?![\\p{L}\\p{N}_])` : source;
  //: A regular expression reads as it does in the find panel it may have come from (D33): `^` and `$` are
  //: a line's ends (`m`), and `\p{L}` reads (`u`). A pattern only valid without `u` still reads (whole word needs `u`).
  const tries = regex ? (word ? [`${flags}mu`] : [`${flags}mu`, `${flags}m`]) : [word ? `${flags}u` : flags];
  let failure = null;
  for (const set of tries) {
    try {
      return new RegExp(wrapped, set);
    } catch (error) {
      failure ||= error;
    }
  }
  return { error: failure.message };
}

//: `carry` is the find panel's query (D33: one entry point): its words, replacement and three options become the dialog's.
async function docReplaceOpen(carry = null) {
  if (docDirty) await saveDocument({ silent: true });
  const dialog = $("doc-replace-dialog");
  if (!dialog) return;
  if (!dialog.open) dialog.showModal();
  const view = docCmView;
  const picked = view && !view.state.selection.main.empty ? view.state.sliceDoc(view.state.selection.main.from, view.state.selection.main.to).split("\n")[0] : "";
  if (picked) $("doc-replace-find").value = picked;
  if (carry && typeof carry.find === "string" && carry.find) {
    $("doc-replace-find").value = carry.find;
    $("doc-replace-with").value = carry.replace || "";
    $("doc-replace-case").checked = Boolean(carry.caseSensitive);
    $("doc-replace-regex").checked = Boolean(carry.regexp);
    $("doc-replace-word").checked = Boolean(carry.wholeWord);
  }
  $("doc-replace-find").focus();
  $("doc-replace-find").select();
  docReplace.pool = null;
  await renderDocReplace();
}

//: The documents a replace would change, read fresh: the list's own rows hold
//: no text, and a count from stale text would promise a change it cannot make.
//: Read once per opening, not once per keystroke (audit 1028 D12: every
//: pause in the find field downloaded every document again). The pool is the
//: texts the dialog opened on (`openDocReplace` empties it); the dialog's close drops it.
async function docReplaceScan(pattern) {
  const out = [];
  if (!docReplace.pool) docReplace.pool = await apiJson("/documents/contents");
  for (const doc of docReplace.pool) {
    const count = doc.content.match(pattern)?.length || 0;
    if (count) out.push({ ...doc, count });
  }
  return out;
}

function docReplaceDisarm() {
  const run = $("doc-replace-run");
  if (run?.dataset.armed !== "1") return;
  run.dataset.armed = "";
  run.textContent = "Replace all";
  $("doc-replace-summary").textContent = run.dataset.was || "";
}

async function renderDocReplace() {
  const summary = $("doc-replace-summary");
  const list = $("doc-replace-list");
  const run = $("doc-replace-run");
  docReplaceDisarm();
  const pattern = docReplacePattern();
  list.replaceChildren();
  run.disabled = true;
  docReplace.matches = [];
  clearTimeout(docReplace.late);
  if (!pattern || pattern.error) {
    //: A pattern half-typed ("(" , "[a-") is not wrong yet: its error waits for a pause (INBOX 1579).
    summary.textContent = pattern?.error ? "" : "Type what to find.";
    if (pattern?.error) docReplace.late = setTimeout(() => (summary.textContent = `That pattern does not read: ${pattern.error}`), 800);
    return;
  }
  summary.textContent = "Searching…";
  const matches = await docReplaceScan(pattern);
  if (String(docReplacePattern()) !== String(pattern)) return;
  docReplace.matches = matches;
  const total = matches.reduce((sum, m) => sum + m.count, 0);
  summary.textContent = matches.length
    ? `${total} match${total === 1 ? "" : "es"} in ${nounCount(matches.length, "document")}.`
    : "No document has it.";
  docReplace.skipped = new Set();
  for (const match of matches) list.appendChild(docReplaceRow(match, pattern));
  run.disabled = !matches.length;
}

//: A row per document: a box to leave it out, and the first match in its
//: line, so a pattern that catches the wrong thing shows before it runs (D29).
function docReplaceRow(match, pattern) {
  const row = document.createElement("li");
  row.className = "doc-ai-history-entry doc-replace-row";
  const label = document.createElement("label");
  label.className = "row align-center checkbox-label small";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = true;
  box.addEventListener("change", () => {
    docReplace.skipped[box.checked ? "delete" : "add"](match.id);
    $("doc-replace-run").disabled = docReplace.matches.every((m) => docReplace.skipped.has(m.id));
    docReplaceDisarm();
  });
  const name = document.createElement("span");
  name.textContent = `${match.title || "Untitled"} · ${match.count}`;
  label.append(box, name);
  const snippet = document.createElement("span");
  snippet.className = "muted text-sm doc-replace-snippet";
  snippet.textContent = docReplaceSnippet(match.content, pattern);
  row.append(label, snippet);
  return row;
}

function docReplaceSnippet(text, pattern) {
  pattern.lastIndex = 0;
  const hit = pattern.exec(text);
  pattern.lastIndex = 0;
  if (!hit) return "";
  const from = Math.max(0, hit.index - 30);
  const to = Math.min(text.length, hit.index + hit[0].length + 30);
  return `${from ? "…" : ""}${text.slice(from, to).replace(/\s+/g, " ")}${to < text.length ? "…" : ""}`;
}

//: Each write carries the hash of the text it was worked out from and keeps
//: the hashes it gets back in `hashes`, so an undo or redo after one of these
//: documents was edited is refused whole instead of writing over the edit
//: (audit 1028 D11).
async function docWriteContents(items, hashes, keep = false) {
  const sent = items.map((item) => ({ ...item, base_hash: hashes[item.id] || null }));
  const res = await apiJson("/documents/contents", { method: "POST", body: JSON.stringify({ documents: sent }) });
  Object.assign(hashes, res.hashes || {});
  const open = items.find((item) => item.id === currentDoc?.id);
  if (open) docShowSaved(await apiJson(`/documents/${open.id}`), keep);
  loadDocuments(currentDoc?.id);
}

async function runDocReplace() {
  const pattern = docReplacePattern();
  const chosen = docReplace.matches.filter((m) => !docReplace.skipped?.has(m.id));
  if (!pattern || pattern.error || !chosen.length) return;
  //: A plain replace is plain: `$&` and `$1` mean something only to a pattern.
  const typed = $("doc-replace-with").value;
  const replacement = $("doc-replace-regex").checked ? typed : typed.replace(/\$/g, "$$$$");
  const before = chosen.map((m) => ({ id: m.id, content: m.content }));
  const after = chosen.map((m) => ({ id: m.id, content: m.content.replace(pattern, replacement) }));
  const total = chosen.reduce((sum, m) => sum + m.count, 0);
  const hashes = Object.fromEntries(chosen.map((m) => [m.id, m.content_hash]));
  //: More than one document changing is said before it happens (1031 DC4:
  //: 357 matches in 3 documents ran at once, the toast's Undo the only guard).
  //: In the dialog, on the button, because a confirm dialog opens behind a
  //: modal one: the first press asks, the second replaces, and any change to
  //: the find, the options or the ticks puts the label back.
  const run = $("doc-replace-run");
  if (after.length > 1 && run.dataset.armed !== "1") {
    run.dataset.armed = "1";
    run.dataset.was = $("doc-replace-summary").textContent;
    run.textContent = `Replace in ${nounCount(after.length, "document")}`;
    $("doc-replace-summary").textContent = `${nounCount(total, "match", "matches")} in ${nounCount(after.length, "document")} change. Press again to replace; Undo takes it all back.`;
    return;
  }
  try {
    await docWriteContents(after, hashes, true);
  } catch (error) {
    return toast(error.message || voiceLine("failed", { what: "replace", why: "nothing was changed" }), true);
  }
  docReplaceDisarm();
  $("doc-replace-dialog").close();
  offerUndo(
    `Replaced ${total} in ${nounCount(after.length, "document")}`,
    `Replaced ${total} in ${nounCount(after.length, "document")}. Undo takes it all back.`,
    () => docWriteContents(before, hashes),
    () => docWriteContents(after, hashes)
  );
}

for (const id of ["doc-replace-find", "doc-replace-regex", "doc-replace-case", "doc-replace-word"]) {
  $(id)?.addEventListener(id === "doc-replace-find" ? "input" : "change", () => {
    clearTimeout(docReplace.timer);
    docReplace.timer = setTimeout(renderDocReplace, 250);
  });
}
$("doc-replace-run")?.addEventListener("click", runDocReplace);
$("doc-replace-dialog")?.addEventListener("close", () => { docReplace.pool = null; });
$("doc-replace-with")?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !$("doc-replace-run").disabled) runDocReplace();
});
