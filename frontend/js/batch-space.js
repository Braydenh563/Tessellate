// batch-space.js: a selection's Move to space (WORLD_CLASS_PLAN row 30,
// section 5), its space picker and its Undo. Out of skills.js on 2026-10-05
// to leave the boot (tests/test_boot_budget.py): it runs only from the
// selection bar's More menu. Loaded by `LAZY_MODULES.batchSpace` (app.js),
// whose stand-ins for `batchMoveToSpace` and `rmSpace` fetch it and calls the real one.

//: **Move the selection to another space** (WORLD_CLASS_PLAN 5 item 5, INBOX
//: 1: a note filed into the wrong space could only leave it with the space).
//: The server moves what hangs off each note too and answers with where each
//: one was, which is what the Undo sends back. Each request names the space
//: the notes are in now, since a note moved out of the space on screen is
//: one this window's own space filter no longer sees.
function batchSpaceRequest(spaceId, ids, from) {
  return api(`/spaces/${encodeURIComponent(spaceId)}/move-notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Auth-Token": authToken(), "X-Workspace-ID": from },
    body: JSON.stringify({ ids }),
  }).then((r) => r.json());
}

function pickSpaceDialog(title) {
  return new Promise((resolve) => {
    const shell = pickerDialog({ title, placeholder: "Search your spaces…", searchLabel: "Search your spaces" });
    const box = pickerListbox(shell, "Your spaces");
    const paint = () => {
      const needle = shell.search.value.trim().toLowerCase();
      const items = spacesCache
        .filter((s) => !needle || s.name.toLowerCase().includes(needle))
        .map((s) => ({
          icon: `ph:${String(s.icon || "ph-folder").replace(/^ph-/, "")}`,
          label: s.name,
          about: s.id === activeSpaceId() ? "The space you are in" : "",
          value: s,
        }));
      box.fill(items, needle, needle ? "No space has that name." : "No spaces yet.");
    };
    shell.search.addEventListener("input", paint);
    paint();
    shell.open(resolve);
  });
}

async function batchMoveToSpace() {
  const ids = batchSelection();
  if (!ids.length) return;
  if (!spacesCache.length) await loadSpaces().catch(() => {});
  const space = await pickSpaceDialog(`Move ${batchNoun(ids)} to which space?`);
  if (!space) return;
  let moved;
  try {
    moved = await batchSpaceRequest(space.id, ids, activeSpaceId());
  } catch (error) {
    toast(error.message, true);
    return;
  }
  exitSelectMode();
  await refreshEntries(ids);
  if (!moved.moved) return toast(`They are all in ${space.name} already.`);
  const back = async () => {
    const groups = new Map();
    for (const [id, from] of Object.entries(moved.from)) groups.set(from, [...(groups.get(from) || []), Number(id)]);
    for (const [from, group] of groups) await batchSpaceRequest(from, group, space.id);
    await refreshEntries(ids);
  };
  const again = async () => {
    await batchSpaceRequest(space.id, Object.keys(moved.from).map(Number), SPACE_ALL);
    await refreshEntries(ids);
  };
  const action = pushUndo(`Moved ${batchNoun(ids)} to ${space.name}`, back, again);
  toastAction(`Moved ${moved.moved} to ${space.name}.`, "Undo", async () => {
    settleUndoFromToast(action);
    await back();
  });
}

// --- delete a space (audit 1029 X5; out of spaces-find.js to keep the boot small) ---

function rmSpace(id) {
  $("space-delete-id").value = id;
  $("space-delete-error").textContent = "";
  //: Delete everything, or move it all to another space first (owner,
  //: 0.3.31). The safe option is selected (audit 1029 X5): the move to the
  //: default space, with the count of what the other option would take.
  const fate = $("space-delete-fate");
  fate.replaceChildren();
  const wipe = document.createElement("option");
  wipe.value = "";
  wipe.textContent = "Delete everything in it";
  fate.appendChild(wipe);
  for (const space of spacesCache) {
    if (space.id === id || space.id === "all") continue;
    const option = document.createElement("option");
    option.value = space.id;
    option.textContent = `Move everything to ${space.name}`;
    fate.appendChild(option);
  }
  const safe = [...fate.options].find((o) => o.value === "default") || fate.options[1];
  if (safe) fate.value = safe.value;
  const count = $("space-delete-count");
  count.textContent = "Counting what is in it.";
  const sync = () => {
    $("space-delete-submit").textContent = fate.value ? "Move and delete space" : "Delete space and contents";
  };
  fate.onchange = sync;
  sync();
  $("space-delete-submit").onclick = spaceDeleteSubmit;
  $("space-delete-dialog").showModal();
  //: The select is rebuilt by enhanceSelect: its opener takes focus.
  (fate.closest(".select-shell")?.querySelector(".select-opener") || fate).focus();
  apiJson(`/spaces/${encodeURIComponent(id)}/counts`).then((c) => {
    const part = (n, one) => `${n} ${one}${n === 1 ? "" : "s"}`;
    const text = `${part(c.notes, "note")}, ${part(c.documents, "document")}`;
    count.textContent = `In this space: ${text}.`;
    wipe.textContent = `Delete everything in it (${text})`;
  }).catch(() => { count.textContent = ""; });
}

async function spaceDeleteSubmit() {
  const id = $("space-delete-id").value;
  const error = $("space-delete-error");
  error.textContent = "";
  try {
    const moveTo = $("space-delete-fate").value;
    const query = moveTo ? `?move_to=${encodeURIComponent(moveTo)}` : "";
    const wasOpen = activeSpaceId() === id;
    const gone = await apiJson(`/spaces/${encodeURIComponent(id)}${query}`, { method: "DELETE" });
    //: The moved notes by id (`refreshEntries` reads the notebook whole
    //: if it cannot patch them in safely).
    if (moveTo) await refreshEntries(gone?.restore?.moved?.entries || []);
    $("space-delete-dialog").close();
    // Standing in the space you just deleted has to move you somewhere real,
    // and reload() alone would leave the header naming a space that is gone.
    if (activeSpaceId() === id) setActiveSpace("default");
    else await loadSpaces();
    //: Undo (undo-1005) when the delete lost nothing: an empty space, or one
    //: whose contents moved, which go back row by row. A delete that took
    //: the contents with it has no Undo (`restore` is null): its files are
    //: gone from the disk, which is why the dialog asks first. Deleting the
    //: open space reloads the page, which empties the stack, so none then.
    let restore = wasOpen ? null : gone?.restore;
    if (restore) {
      const remake = async () => {
        await apiJson("/spaces/restore", { method: "POST", body: JSON.stringify(restore) });
        await loadSpaces();
        if (moveTo) await refreshEntries(restore.moved?.entries || []);
      };
      const action = pushUndo(`Deleted the space “${gone.name}”`, remake, async () => {
        restore = (await apiJson(`/spaces/${encodeURIComponent(id)}${query}`, { method: "DELETE" })).restore || restore;
        await loadSpaces();
        if (moveTo) await refreshEntries(restore.moved?.entries || []);
      });
      toastAction(`Deleted “${gone.name}”.`, "Undo", async () => {
        settleUndoFromToast(action);
        await remake().catch((e) => toast(e.message, true));
      });
    }
  } catch (err) {
    error.textContent = err.message;
  }
}
