// whiteboard-history.js: a board's time machine (2026-10-05, the features
// audit's W2; WHITEBOARD_PLAN decision 33).
//
// Board, History… puts a slider at the foot of the board over its event log
// (`routes_board_history.py`): drag it back and the board is drawn as it was
// then, a moment at a time (a moment is a run of changes no longer than two
// minutes); the two buttons put the whole board back, or only what was
// selected when History opened, as one Undo step; the X, Esc or the slider's
// far right end come back to now.
//
// **A preview is the real renderer drawing the past.** `wbState` is swapped
// for the moment's rows and the board renders as usual, so a past board
// looks exactly like a board, maps included. Nothing may write while it is
// shown: the board's layers take no pointer (the presenting host class,
// does), the board's keys are held off (a capture listener, as presenting
// does), and any write to `/whiteboard/` that slips through is refused
// before it is sent (`wbHistGuard`), so no path can save a past row over a
// present one. Closing fetches the board afresh, so whatever changed on it
// meanwhile (an agent, another tab) is what comes back.
//
// Loaded in the Library bundle after whiteboard-interchange.js
// (`LAZY_MODULES`); its top level is this file's one state object and its
// listeners.

const wbHist = {
  open: false,
  boardId: null,
  moments: [],
  more: false,
  pos: 0,
  keys: [],
  token: 0,
  timer: 0,
  shown: null,
  focus: null,
  realApi: null,
};

const WB_HIST_BAR = "wb-history-bar";

function wbHistBoardParam() {
  return `board_id=${wbHist.boardId ?? 0}`;
}

//: The moment the slider is on, or null at its right end (now). The slider
//: runs oldest (0) to now (`moments.length`); `moments` is newest first.
function wbHistMoment(pos = wbHist.pos) {
  const n = wbHist.moments.length;
  return pos >= n ? null : wbHist.moments[n - 1 - pos] || null;
}

//: "12 minutes ago: 3 added, 1 changed", from the moment's own counts.
function wbHistWords(moment) {
  if (!moment) return "Now";
  const parts = [];
  if (moment.added) parts.push(`${moment.added} added`);
  if (moment.changed) parts.push(`${moment.changed} changed`);
  if (moment.removed) parts.push(`${moment.removed} removed`);
  const when = relativeTime(moment.at);
  return `${when}: ${parts.join(", ") || "a change"}${moment.kept ? "" : " (not kept in full)"}`;
}

//: Writes to the board refused while the past is on screen, before they go.
function wbHistGuard(on) {
  if (on && !wbHist.realApi) {
    const real = window.apiJson;
    wbHist.realApi = real;
    window.apiJson = (path, options = {}) => {
      const method = String(options.method || "GET").toUpperCase();
      if (wbHist.open && method !== "GET" && /^\/whiteboard\//.test(String(path))) {
        toast("The board is showing an earlier version. Put it back, or press Esc to come back to now.");
        return Promise.reject(new Error("The board is showing an earlier version."));
      }
      return real(path, options);
    };
  } else if (!on && wbHist.realApi) {
    window.apiJson = wbHist.realApi;
    wbHist.realApi = null;
  }
}

function wbHistSync() {
  const slider = document.getElementById("wb-history-slider");
  const when = document.getElementById("wb-history-when");
  const moment = wbHistMoment();
  const words = wbHistWords(moment);
  if (slider) {
    slider.max = String(wbHist.moments.length);
    slider.value = String(wbHist.pos);
    slider.setAttribute("aria-valuetext", words);
  }
  if (when) {
    when.textContent = words;
    when.title = moment ? whenText(moment.at) : "";
  }
  const canRestore = Boolean(moment && moment.kept && wbHist.shown === moment.id);
  const whole = document.getElementById("wb-history-restore");
  const some = document.getElementById("wb-history-restore-selection");
  if (whole) whole.disabled = !canRestore;
  if (some) some.disabled = !canRestore || !wbHist.keys.length;
}

async function wbOpenHistory() {
  if (wbHist.open) return;
  const boardId = window.currentBoardId ?? null;
  let page = null;
  try {
    page = await apiJson(`/whiteboard/history?board_id=${boardId ?? 0}`);
  } catch (error) {
    toast(error.message || "The board's history could not be read.", true);
    return;
  }
  if (!page?.moments?.length) {
    toast("Nothing has changed on this board yet, so there is no earlier version to go back to.");
    return;
  }
  Object.assign(wbHist, {
    open: true,
    boardId,
    moments: page.moments,
    more: Boolean(page.more),
    pos: page.moments.length,
    keys: [...wbSelectedKeys()],
    shown: null,
    focus: document.activeElement,
  });
  clearWbSelection();
  wbHistGuard(true);
  document.getElementById("library-view-whiteboard")?.classList.add("wb-presenting");
  document.getElementById(WB_HIST_BAR)?.classList.remove("hidden");
  wbHistSync();
  wbAnnounce(`History: ${page.moments.length} moments. Drag the slider or press the Left arrow to go back.`);
  document.getElementById("wb-history-slider")?.focus({ preventScroll: true });
}

//: Older moments, when the slider reaches the oldest one loaded.
async function wbHistLoadOlder() {
  if (!wbHist.more || !wbHist.moments.length) return;
  const oldest = wbHist.moments[wbHist.moments.length - 1];
  let page = null;
  try {
    page = await apiJson(`/whiteboard/history?${wbHistBoardParam()}&before=${oldest.first_id}`);
  } catch {
    return;
  }
  if (!wbHist.open || !page?.moments?.length) {
    wbHist.more = false;
    return;
  }
  wbHist.moments = [...wbHist.moments, ...page.moments];
  wbHist.more = Boolean(page.more);
  wbHist.pos += page.moments.length;
  wbHistSync();
}

//: Show slider position `pos`: the moment's rows, drawn by the board, or now.
//: Debounced, and a reply that arrives after a newer request is dropped.
function wbHistShow(pos) {
  if (!wbHist.open) return;
  wbHist.pos = Math.max(0, Math.min(wbHist.moments.length, pos));
  wbHist.shown = null;
  wbHistSync();
  clearTimeout(wbHist.timer);
  const token = ++wbHist.token;
  wbHist.timer = setTimeout(async () => {
    const moment = wbHistMoment();
    if (!moment) {
      await fetchWhiteboardState();
      if (token !== wbHist.token || !wbHist.open) return;
      renderWhiteboardNow();
      wbHistSync();
      return;
    }
    if (wbHist.pos === 0) wbHistLoadOlder();
    if (!moment.kept) return;
    let rows = null;
    try {
      rows = await apiJson(`/whiteboard/history/${moment.id}?${wbHistBoardParam()}`);
    } catch (error) {
      if (token === wbHist.token) toast(error.message || "That moment could not be read.", true);
      return;
    }
    if (token !== wbHist.token || !wbHist.open) return;
    wbState = { ...wbState, nodes: rows.nodes || [], sketches: rows.sketches || [], objects: rows.objects || [] };
    renderWhiteboardNow();
    wbHist.shown = moment.id;
    wbHistSync();
  }, 120);
}

async function wbCloseHistory({ refetch = true } = {}) {
  if (!wbHist.open) return;
  clearTimeout(wbHist.timer);
  wbHist.token += 1;
  wbHist.open = false;
  wbHistGuard(false);
  document.getElementById("library-view-whiteboard")?.classList.remove("wb-presenting");
  document.getElementById(WB_HIST_BAR)?.classList.add("hidden");
  if (refetch && (window.currentBoardId ?? null) === wbHist.boardId) {
    await fetchWhiteboardState();
    renderWhiteboardNow();
  }
  const focus = wbHist.focus;
  wbHist.focus = null;
  (focus && document.contains(focus) ? focus : document.getElementById("whiteboard-container"))?.focus?.({ preventScroll: true });
}

//: Put the board, or only what was selected, back as it was at the moment
//: shown: one request, then the board read afresh inside a recorded gesture,
//: so the whole restore is one Undo step (`wbRecordGesture`).
async function wbHistRestore(onlySelection) {
  const moment = wbHistMoment();
  if (!moment || wbHist.shown !== moment.id) return;
  const keys = onlySelection ? [...wbHist.keys] : null;
  if (onlySelection && !keys.length) return;
  const words = wbHistWords(moment).split(":")[0];
  const asked = onlySelection
    ? `Put the ${keys.length === 1 ? "selected item" : `${keys.length} selected items`} back as ${keys.length === 1 ? "it was" : "they were"} ${words}?`
    : `Put the whole board back as it was ${words}?`;
  if (!(await confirmDialog(`${asked}\n\nUndo (Ctrl+Z) takes it back, and the change is in the history too.`))) return;
  const boardId = wbHist.boardId;
  await wbCloseHistory({ refetch: false });
  if ((window.currentBoardId ?? null) !== boardId) return;
  //: The board as it is now, before the gesture reads it: the past rows
  //: are still in `wbState` until this.
  await fetchWhiteboardState();
  let counts = null;
  try {
    await wbRecordGesture(async () => {
      counts = await apiJson(`/whiteboard/history/${moment.id}/restore?board_id=${boardId ?? 0}`, {
        method: "POST",
        body: JSON.stringify({ keys }),
      });
      await fetchWhiteboardState();
    });
  } catch (error) {
    toast(error.message || "The board could not be put back.", true);
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return;
  }
  renderWhiteboardNow();
  const done = counts ? [counts.made && `${counts.made} made`, counts.changed && `${counts.changed} changed`, counts.removed && `${counts.removed} removed`].filter(Boolean).join(", ") : "";
  const said = `${onlySelection ? "Selection" : "Board"} put back as it was ${words}${done ? `: ${done}` : ""}. Ctrl+Z undoes it.`;
  wbAnnounce(said);
  toast(said);
}

//: While History is open the keys are its own, ahead of the board's
//: (capture, on the window, as presenting does): the arrows step the
//: moments, Home and End go to the oldest and to now, Esc comes back to now,
//: and nothing else reaches the board (a tool letter, Delete, Ctrl+Z).
window.addEventListener("keydown", (event) => {
  if (!wbHist.open) return;
  const inBar = Boolean(event.target.closest?.(`#${WB_HIST_BAR}`));
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopImmediatePropagation();
    wbCloseHistory();
    return;
  }
  if (event.key === "Tab") return;
  if (inBar) {
    //: The slider's own keys move it (an input event follows); a button's
    //: Enter and Space press it. Only the board's listeners are held off.
    event.stopImmediatePropagation();
    return;
  }
  event.stopImmediatePropagation();
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const step = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[event.key];
  if (step) {
    event.preventDefault();
    wbHistShow(wbHist.pos + step);
  } else if (event.key === "Home") {
    event.preventDefault();
    wbHistShow(0);
  } else if (event.key === "End") {
    event.preventDefault();
    wbHistShow(wbHist.moments.length);
  }
}, true);

document.addEventListener("input", (event) => {
  if (event.target?.id === "wb-history-slider") wbHistShow(Number(event.target.value));
});

document.addEventListener("click", (event) => {
  const button = event.target.closest?.(`#${WB_HIST_BAR} button`);
  if (!button || !wbHist.open || button.disabled) return;
  if (button.id === "wb-history-end") wbCloseHistory();
  else if (button.id === "wb-history-restore") wbHistRestore(false);
  else if (button.id === "wb-history-restore-selection") wbHistRestore(true);
});

// --- A change from elsewhere is one step (Brief 77, WHITEBOARD_PLAN
// "Deepened 2026-10-10" row 3; WORLD_CLASS 28.1 rule 1) -----------------------
//
// An agent's tool or another tab writing to the open board used to change it
// under the stack: the 2026-10-05 audit found neither on it, so Ctrl+Z
// stepped back past them to an older step of one's own. Now the board is read
// afresh inside a recorded gesture (`wbRecordGesture`, as a restore is), so
// whatever the read changed is one entry, named by where it came from, and
// Ctrl+Z puts the board back as it was before it.
//
// Two doorways: the chat stream's board tools (`mm:board-changed`, sent by
// capture-ask.js with `source` "Atlas"), and this tab's own writes told to
// the others over a BroadcastChannel ("Another tab").

const wbElsewhere = { busy: false, pending: null, timer: 0, tab: Math.random().toString(36).slice(2), channel: null };

//: Reads the open board afresh as one Undo step, labelled by `source`.
//: Resolves with the number of items the change touched (0 when the board
//: was already current, or not the board named, or History is showing).
async function wbTakeChangeFromElsewhere(boardId, source) {
  const open = window.currentBoardId ?? null;
  if (wbHist.open || !wbState || String(open) !== String(boardId ?? null)) return 0;
  if (wbElsewhere.busy || wbRecordDepth > 0) {
    wbElsewhere.pending = { boardId, source };
    return 0;
  }
  wbElsewhere.busy = true;
  let count = 0;
  try {
    const top = wbUndoStack[wbUndoStack.length - 1];
    //: The write came past this tab's `api`, so its read cache never heard.
    clearApiCache();
    await wbRecordGesture(async () => {
      await fetchWhiteboardState();
    });
    const entry = wbUndoStack[wbUndoStack.length - 1];
    if (entry && entry !== top) {
      count = entry.action === "batch" ? entry.entries.length : 1;
      entry.label = `${source} changed ${count} ${count === 1 ? "item" : "items"}`;
      renderWhiteboardNow();
      const said = `${entry.label} on this board. Ctrl+Z takes it back.`;
      wbAnnounce(said);
      toast(said);
    }
  } catch (err) {
    recordBrowserLog("WARN", [`[Board] reading a change from ${source}: ${err.message || err}`]);
  } finally {
    wbElsewhere.busy = false;
    const next = wbElsewhere.pending;
    wbElsewhere.pending = null;
    if (next) setTimeout(() => wbTakeChangeFromElsewhere(next.boardId, next.source), 0);
  }
  return count;
}

//: A burst (an agent's several tool calls, a drag that saves twice) is read
//: once, a beat after it ends.
function wbChangeFromElsewhereSoon(boardId, source) {
  clearTimeout(wbElsewhere.timer);
  wbElsewhere.timer = setTimeout(() => wbTakeChangeFromElsewhere(boardId, source), 300);
}

document.addEventListener("mm:board-changed", (event) => {
  const detail = event.detail || {};
  const boardId = detail.boardId ?? window.currentBoardId ?? null;
  wbChangeFromElsewhereSoon(boardId, detail.source || "Atlas");
  //: The agent wrote on the server, past this tab's `apiJson`: the other
  //: tabs hear of it here.
  wbElsewhere.channel?.postMessage({ tab: wbElsewhere.tab, boardId });
});

//: This tab's writes to a board, told to the other tabs. The wrapper sits
//: under History's guard (`wbHistGuard` keeps whatever `apiJson` it finds),
//: and says nothing for a write that failed.
if ("BroadcastChannel" in window) {
  try {
    wbElsewhere.channel = new BroadcastChannel("memorymap-boards");
    wbElsewhere.channel.onmessage = (event) => {
      const data = event.data || {};
      if (data.tab === wbElsewhere.tab) return;
      wbChangeFromElsewhereSoon(data.boardId, "Another tab");
    };
    const real = window.apiJson;
    window.apiJson = async (path, options = {}) => {
      const result = await real(path, options);
      const method = String(options.method || "GET").toUpperCase();
      if (method !== "GET" && /^\/whiteboard\//.test(String(path))) {
        wbElsewhere.channel.postMessage({ tab: wbElsewhere.tab, boardId: window.currentBoardId ?? null });
      }
      return result;
    };
  } catch (err) {
    wbElsewhere.channel = null;
  }
}

// --- Snapshots: the History sheet as a revision list (Brief 77, row 4) ------
//
// draw.io keeps named revisions with a picture of each; the slider above
// shows moments but cannot name one or find it again next week. A snapshot
// is a name on the board's newest event (`routes_board_history.py`); its
// picture is the Library card's own (`mapPreview`) drawn from the board as it
// was then, and Restore is the moment restore inside a recorded gesture, so
// it is one Undo step and Ctrl+Z gives the board back.

//: The past rows as the Library card's preview fields: each item's box in
//: 0..1 of the whole board's, as `_preview_items` sends them.
function wbSnapshotPreviewBoard(rows) {
  const all = [...(rows.objects || []), ...(rows.nodes || []), ...(rows.sketches || [])]
    .filter((r) => Number.isFinite(r.x) && Number.isFinite(r.y));
  if (!all.length) return { preview_items: [] };
  const box = (r) => [r.x, r.y, r.x + (r.width || 40), r.y + (r.height || 30)];
  const xs = all.flatMap((r) => [box(r)[0], box(r)[2]]);
  const ys = all.flatMap((r) => [box(r)[1], box(r)[3]]);
  const [x0, y0] = [Math.min(...xs), Math.min(...ys)];
  const w = Math.max(1, Math.max(...xs) - x0);
  const h = Math.max(1, Math.max(...ys) - y0);
  const items = all.slice(0, 120).map((r) => ({
    x: (r.x - x0) / w,
    y: (r.y - y0) / h,
    w: (r.width || 40) / w,
    h: (r.height || 30) / h,
    kind: rows.sketches?.includes(r) ? "sketch" : "card",
    label: String(r.data?.content || r.text || r.title || "").slice(0, 24),
  }));
  return { preview_items: items, preview_aspect: w / h };
}

//: Puts the board back as it was at `eventId`, as one Undo step.
async function wbRestoreToEvent(boardId, eventId) {
  await fetchWhiteboardState();
  await wbRecordGesture(async () => {
    await apiJson(`/whiteboard/history/${eventId}/restore?board_id=${boardId}`, { method: "POST", body: JSON.stringify({ keys: null }) });
    await fetchWhiteboardState();
  });
  renderWhiteboardNow();
}

function wbSnapshotRow(snap, boardId, redraw, close) {
  const row = document.createElement("div");
  row.className = "wb-snapshot-row";
  const picture = document.createElement("div");
  picture.className = "wb-snapshot-preview";
  apiJson(`/whiteboard/history/${snap.event_id}?board_id=${boardId}`, { silent: true })
    .then((rows) => {
      picture.append(mapPreview(wbSnapshotPreviewBoard(rows), { size: "card" }));
    })
    .catch(() => picture.classList.add("is-gone"));
  const words = document.createElement("div");
  words.className = "wb-snapshot-words";
  const name = document.createElement("strong");
  name.textContent = snap.name;
  const when = document.createElement("span");
  when.className = "muted";
  when.textContent = relativeTime(snap.at);
  words.append(name, when);
  const restore = smallButton("ph:arrow-counter-clockwise Restore", `Put the board back as it was at "${snap.name}"; Ctrl+Z takes it back`, async () => {
    close();
    try {
      await wbRestoreToEvent(boardId, snap.event_id);
      const said = `Board put back as it was at "${snap.name}". Ctrl+Z undoes it.`;
      wbAnnounce(said);
      toast(said);
    } catch (err) {
      toast(err.message || "The board could not be put back.", true);
      await fetchWhiteboardState();
      renderWhiteboardNow();
    }
  });
  const remove = smallButton("ph:trash", `Delete the snapshot "${snap.name}" (the board is not changed)`, async () => {
    await apiJson(`/whiteboard/history/snapshots/${snap.id}?board_id=${boardId}`, { method: "DELETE" }).catch((err) => toast(err.message, true));
    redraw();
  });
  row.append(picture, words, restore, remove);
  return row;
}

async function wbOpenSnapshots() {
  const boardId = window.currentBoardId;
  if (!boardId) {
    toast("The scratch board keeps no snapshots. Open or make a named board first.");
    return;
  }
  openSheet({
    label: "Snapshots",
    name: "wb-snapshots",
    build: (card, close) => {
      card.classList.add("wb-snapshots-card");
      const save = smallButton("ph:camera Save a snapshot…", "Name the board as it is now, to come back to", async () => {
        const at = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        const name = await promptDialog("Name this snapshot", `Snapshot ${at}`, { confirmLabel: "Save" });
        if (name === null || name === undefined) return;
        try {
          await apiJson("/whiteboard/history/snapshots", { method: "POST", body: JSON.stringify({ board_id: boardId, name: String(name).trim() || `Snapshot ${at}` }) });
          redraw();
        } catch (err) {
          toast(err.message || "The snapshot was not saved.", true);
        }
      }, false);
      save.id = "wb-snapshot-save";
      const list = document.createElement("div");
      list.className = "sheet-list wb-snapshot-list";
      const redraw = async () => {
        const out = await apiJson(`/whiteboard/history/snapshots?board_id=${boardId}`, { silent: true }).catch(() => ({ snapshots: [] }));
        const rows = (out.snapshots || []).map((snap) => wbSnapshotRow(snap, boardId, redraw, close));
        if (!rows.length) {
          const empty = document.createElement("p");
          empty.className = "muted";
          empty.textContent = "No snapshots yet. Save one before a big change, and Restore puts the board back.";
          rows.push(empty);
        }
        list.replaceChildren(...rows);
      };
      card.append(save, list);
      redraw();
    },
  });
}
