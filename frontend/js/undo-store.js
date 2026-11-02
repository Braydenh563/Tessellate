// undo-store.js: the undo histories that survive a reload.
//
// **Each board, map and document keeps its last hundred steps across a
// reload** (INBOX 553(b), the owner's decision of 2026-10-05; WHITEBOARD_PLAN
// decision 17 as amended). Before this the histories lived for the session
// only: a reload, the desktop window closed and opened, or the app updating
// itself took Ctrl+Z away from whatever had just been done.
//
// **In IndexedDB, on this device, not on the server.** An undo step is an
// instruction against what this device last saw ("put topic 41 back where it
// was"), so a history carried to another device would be replayed over a
// board it never described; and this way nothing about it needs a schema,
// a migration or a network. Keyed `board:<id>` and `doc:<id>`, one record
// each, written a moment after the stacks change and never more often. The
// lock empties the store with everything else the lock purges, since a
// document's history holds its text.
//
// Loaded with the Library bundle (app.js `LAZY_MODULES.library`), ahead of
// the two files that call it, and every call site guards with `typeof` so a
// browser without IndexedDB (or a private window that refuses it) simply
// keeps the session-only behaviour.

const UNDO_STORE_DB = "memorymap-undo";
const UNDO_STORE_TABLE = "stacks";
//: The steps kept per board and per document: the owner's "~100".
const UNDO_STORE_MAX = 100;
//: How long the stacks have to be still before they are written.
const UNDO_STORE_DELAY_MS = 600;

let undoStoreOpening = null;

function undoStoreDb() {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  if (!undoStoreOpening) {
    undoStoreOpening = new Promise((resolve) => {
      let request;
      try {
        request = indexedDB.open(UNDO_STORE_DB, 1);
      } catch {
        resolve(null);
        return;
      }
      request.onupgradeneeded = () => request.result.createObjectStore(UNDO_STORE_TABLE);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
      request.onblocked = () => resolve(null);
    });
  }
  return undoStoreOpening;
}

function undoStoreRequest(mode, act) {
  return undoStoreDb().then((db) => new Promise((resolve) => {
    if (!db) {
      resolve(null);
      return;
    }
    try {
      const request = act(db.transaction(UNDO_STORE_TABLE, mode).objectStore(UNDO_STORE_TABLE));
      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  }));
}

//: The stored record for a key, or null.
function undoStoreGet(key) {
  return undoStoreRequest("readonly", (table) => table.get(String(key)));
}

const undoStoreTimers = new Map();

//: Written a moment later, the latest value winning, as plain data: the
//: stacks can hold anything a step needed in memory, and only what survives
//: a JSON round trip is a step that can be replayed after a reload.
//: `value` may be a function, called only when the write runs: a caller
//: with a costly snapshot (a whole editor history) pays for it once per
//: pause instead of on every keystroke (audit 1028 D6).
function undoStorePut(key, value) {
  const name = String(key);
  clearTimeout(undoStoreTimers.get(name));
  undoStoreTimers.set(name, setTimeout(() => {
    undoStoreTimers.delete(name);
    let plain;
    try {
      plain = JSON.parse(JSON.stringify(value instanceof Function ? value() : value));
    } catch {
      return;
    }
    undoStoreRequest("readwrite", (table) => table.put(plain, name));
  }, UNDO_STORE_DELAY_MS));
}

//: Everything, for the lock (and nothing else ever needs it).
function undoStoreClear() {
  for (const timer of undoStoreTimers.values()) clearTimeout(timer);
  undoStoreTimers.clear();
  return undoStoreRequest("readwrite", (table) => table.clear());
}

//: A board's two stacks, trimmed to the last hundred steps each.
function undoStoreBoardValue(undo, redo) {
  //: A "call" step holds two functions (whiteboard.js `wbPushCall`), which
  //: IndexedDB cannot store and which mean nothing after a reload.
  const keep = (steps) => steps.filter((step) => step.action !== "call").slice(-UNDO_STORE_MAX);
  return { undo: keep(undo), redo: keep(redo), at: Date.now() };
}
