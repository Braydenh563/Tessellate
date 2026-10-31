// The undo kit (INBOX 898, undo everywhere), loaded on the first act that
// needs it (`LAZY_MODULES.undoKit`, app.js) so the boot scripts stay inside
// their gzip budget. Each helper puts one step on the stack through
// `pushUndo` (status.js), the one contract (tests/test_undo_contract.py); the
// writes it covers are held to it by tests/test_undo_coverage.py. A caller
// that reads the returned step awaits it, because until this file has loaded
// the name is a stand-in that answers a promise.

//: **A note this act made** (INBOX 898, undo everywhere): Undo bins it, Redo
//: brings it back. The one shape every "save as a note" path uses, so a note
//: made from a chat answer, a web page, the graph or a wiki link is as
//: reversible as one typed into Capture.
function pushEntryCreateUndo(entry, label = "Created a note") {
  const id = entry?.id;
  if (!id) return null;
  return pushUndo(
    label,
    async () => {
      await api(`/entries/${id}`, { method: "DELETE" });
      await refreshEntries([id]);
    },
    async () => {
      await api(`/entries/${id}/restore`, { method: "POST" });
      await refreshEntries([id]);
    }
  );
}

//: **A link this act made** (INBOX 898): Undo removes that very link by its
//: id (a pair can be linked twice by different routes, and guessing is how an
//: undo deletes the wrong one), Redo makes it again and keeps the new id.
//: `made` is the server's answer to the POST, `body` what was posted.
function pushLinkCreateUndo(sourceId, targetId, made, body, label = "Linked two notes", after) {
  let liveId = made?.links?.find((link) => link.entry_id === targetId)?.link_id ?? null;
  const settle = async () => {
    await refreshEntries([sourceId, targetId]).catch(() => {});
    await after?.();
  };
  return pushUndo(
    label,
    async () => {
      if (liveId == null) return;
      await api(`/entries/${sourceId}/links/${liveId}`, { method: "DELETE" });
      await settle();
    },
    async () => {
      const redone = await apiJson(`/entries/${sourceId}/links`, { method: "POST", body: JSON.stringify(body) });
      liveId = redone?.links?.find((link) => link.entry_id === targetId)?.link_id ?? liveId;
      await settle();
    }
  );
}

//: **Any write whose inverse is the same request with the old value** (INBOX
//: 898): a rename, a pin, a colour, a move, a flag. `before` and `after` are
//: the two request bodies; `refresh` repaints whatever showed it.
function pushRequestUndo(label, path, method, before, after, refresh) {
  const send = async (body) => {
    await api(path, { method, body: JSON.stringify(body) });
    await refresh?.();
  };
  return pushUndo(label, () => send(before), () => send(after));
}

//: **Several notes written at once** (a bulk tag, a bulk move, a bulk flag):
//: one step on the stack that puts each note's own fields back. `changes` is
//: `[{ id, before, after }]` with the PUT bodies.
function pushEntriesPutUndo(label, changes, after) {
  const putEach = async (key) => {
    for (const change of changes) await api(`/entries/${change.id}`, { method: "PUT", body: JSON.stringify(change[key]) });
    await refreshEntries(changes.map((change) => change.id)).catch(() => {});
    await after?.();
  };
  return pushUndo(label, () => putEach("before"), () => putEach("after"));
}

//: **A bin and its restore** (INBOX 898): `restored` says which way the act
//: went. Putting something back from the bin is undone by binning it again,
//: and binning is undone by putting it back, so one helper serves both.
function pushBinPairUndo(label, binPath, restorePath, restored, refresh) {
  const bin = async () => {
    await api(binPath, { method: "DELETE" });
    await refresh?.();
  };
  const restore = async () => {
    await api(restorePath, { method: "POST" });
    await refresh?.();
  };
  return restored ? pushUndo(label, bin, restore) : pushUndo(label, restore, bin);
}

//: **Two routes that undo each other** (archive and unarchive, pin and unpin,
//: hide and show): `back` and `again` are `[path, method]` pairs, or lists of
//: them for a bulk act; a third item is the request body.
function pushRoutePairUndo(label, back, again, refresh) {
  const run = (routes) => async () => {
    const list = Array.isArray(routes[0]) ? routes : [routes];
    for (const [path, method, body] of list) await api(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
    await refresh?.();
  };
  return pushUndo(label, run(back), run(again));
}

//: **Deciding a contradiction** (accept, or "not a contradiction"): Undo asks
//: the server to reopen the pair (`/entries/tensions/reopen`), which also takes
//: the `contradicts` link away when this accept made it and drops what the
//: decision taught the learning loop; Redo decides it again.
function pushTensionLinkUndo(earlierId, laterId, verdict = "accept", made = true) {
  const pair = { earlier_id: earlierId, later_id: laterId };
  const post = (path, body) => apiJson(path, { method: "POST", body: JSON.stringify(body) });
  const settle = () => refreshEntries([earlierId, laterId]).catch(() => {});
  return pushUndo(
    verdict === "accept" ? "Linked two notes as contradicting" : "Said two notes do not contradict",
    async () => {
      await post("/entries/tensions/reopen", { ...pair, remove_link: verdict === "accept" && made });
      await settle();
    },
    async () => {
      await post(`/entries/tensions/${verdict === "accept" ? "accept" : "dismiss"}`, pair);
      await settle();
    }
  );
}

//: **A delete the server kept in its undo bin** (core/undo_bin.py, INBOX
//: 898): a picture, a file, a past question, what was learned, a board
//: library. Each item is `{ del: [path, method, body?], restore, token }`:
//: Undo posts `{ token }` to `restore`, Redo sends the delete again and
//: keeps the new token it answers with. `refresh` repaints whatever showed it.
function pushTokenUndo(label, items, refresh, message) {
  const list = items.filter((item) => item?.token);
  if (!list.length) return null;
  const send = ([path, method, body]) => apiJson(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
  const undo = async () => {
    for (const item of list) await apiJson(item.restore, { method: "POST", body: JSON.stringify({ token: item.token }) });
    await refresh?.();
  };
  const redo = async () => {
    for (const item of list) item.token = (await send(item.del))?.undo_token ?? item.token;
    await refresh?.();
  };
  //: With a `message` the step also gets the toast whose Undo is this entry.
  return message ? offerUndo(label, message, undo, redo) : pushUndo(label, undo, redo);
}

//: **An upload as one step** (the Library's Upload, a picture added to a
//: chat or a board): Undo moves the file to the bin, Redo brings it back.
//: `base` is `/media` or `/files`; `made` is the upload's answer.
function pushUploadUndo(label, base, made, refresh) {
  if (made?.id == null) return null;
  let id = made.id;
  let token = null;
  return pushUndo(
    label,
    async () => {
      token = (await apiJson(`${base}/${id}`, { method: "DELETE" }))?.undo_token ?? null;
      await refresh?.();
    },
    async () => {
      if (token) id = (await apiJson(`${base}/restore`, { method: "POST", body: JSON.stringify({ token }) }))?.id ?? id;
      await refresh?.();
    }
  );
}

//: **A correction this act recorded** (a dismissed suggestion, a verdict
//: on an answer): Undo takes that one row back by the id the POST answered
//: with, Redo records it again.
function pushCorrectionUndo(label, body, made, refresh) {
  let id = made?.id;
  if (id == null) return null;
  return pushUndo(
    label,
    async () => {
      await api(`/learned/corrections/${id}`, { method: "DELETE" });
      await refresh?.();
    },
    async () => {
      id = (await apiJson("/learned/corrections", { method: "POST", body: JSON.stringify(body) }))?.id ?? id;
      await refresh?.();
    }
  );
}

//: **Something this act made, whose inverse is deleting it** (a card put on
//: a board, a space, a recording): Undo deletes it through `deletePath(made)`,
//: Redo makes it again from the same request and keeps the new answer, so
//: the next Undo deletes that one. `make` is `[path, method, body]`.
function pushMadeUndo(label, make, made, deletePath, refresh) {
  if (!made) return null;
  let live = made;
  return pushUndo(
    label,
    async () => {
      await api(deletePath(live), { method: "DELETE" });
      await refresh?.();
    },
    async () => {
      live = await apiJson(make[0], { method: make[1], body: JSON.stringify(make[2]) });
      await refresh?.();
    }
  );
}

//: **Text put into a box by an act that is not typing** (a file dropped
//: into a note, a picture pasted): Undo writes the box as it was, Redo as it
//: became, and the box is told it changed so its editor and draft follow.
function pushTextUndo(label, box, before, after) {
  const put = (value) => () => {
    box.value = value;
    box.dispatchEvent(new Event("input", { bubbles: true }));
  };
  return pushUndo(label, put(before), put(after));
}

//: **`[[old]]` rewritten as the new name in other notes** (a renamed note's
//: offer): the answer names each note changed and the version it held before.
//: Undo puts those versions back; Redo rewrites again, and keeps the new list.
function pushWikiRenameUndo(entryId, old, done) {
  const notes = done?.notes || [];
  if (!notes.length) return null;
  const settle = () => refreshEntries(notes.map((note) => note.id)).catch(() => {});
  return pushUndo(
    `Renamed [[${old}]] in ${nounCount(notes.length, "note")}`,
    async () => {
      for (const note of notes) await api(`/entries/${note.id}/history/${note.revision_id}/restore`, { method: "POST" });
      await settle();
    },
    async () => {
      const again = await apiJson(`/entries/${entryId}/wiki-rename`, { method: "POST", body: JSON.stringify({ old }) });
      notes.splice(0, notes.length, ...(again.notes || []));
      await settle();
    }
  );
}
