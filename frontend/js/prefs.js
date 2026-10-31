// prefs.js: the one reader of this browser's saved settings (WORLD_CLASS_PLAN
// section 10, F1). Loaded right after app.js.
//
// The class of bug this exists for is the worst one the project has had: two
// appearance settings missing a default wrote `NaN` into CSS and flattened
// every card in the app, a value invalid where it was used and set somewhere
// else. Beside it, a stored value that is not JSON threw inside `JSON.parse`
// and took the caller's whole init with it. So every read here has three
// promises: it never throws (a blocked or private-mode storage reads as
// empty), it never returns `undefined` (a key with no value gets its schema
// default, or the caller's), and a read that wants a shape (a number, a list,
// an object) gets that shape or the default, never a near miss.
//
// `PREFS_SCHEMA` holds a default and a version for the keys that have been
// moved here. A key whose stored form changes gets its version raised and a
// `migrate(raw)` that turns the old form into the new; `prefsMigrate()` runs
// once at load and records what it has done under `prefs-versions`. The lint
// (`tests/test_prefs_module.py`) holds direct `localStorage.getItem` calls
// at their count per file, a ratchet that only goes down.

//: key -> { default, version, migrate(raw) }. Defaults only for keys whose
//: absence a caller cannot be trusted to handle (a number that reaches CSS).
const PREFS_SCHEMA = {
  zoom: { default: "100", version: 1 },
  "graph-spread": { default: "50", version: 1 },
  "graph-gravity": { default: "50", version: 1 },
  //: Interface animations: "on" (the default) or "off". Its absence must
  //: read as on, which theme-boot.js and every reader of the attribute rely on.
  "ui-motion": { default: "on", version: 1 },
};

function prefsStore() {
  try {
    return window.localStorage;
  } catch {
    return null; // a sandboxed frame or blocked site data
  }
}

const prefs = {
  //: The stored string, the schema's default, or `fallback`, in that order.
  get(key, fallback = "") {
    let raw = null;
    try {
      raw = prefsStore()?.getItem(key) ?? null;
    } catch {
      raw = null;
    }
    if (raw !== null) return raw;
    const known = PREFS_SCHEMA[key];
    return known && known.default !== undefined ? known.default : fallback;
  },
  //: Whether a value was ever stored, as distinct from the default.
  has(key) {
    try {
      return prefsStore()?.getItem(key) != null;
    } catch {
      return false;
    }
  },
  //: Parsed JSON of the same kind as `fallback` (an array for an array, a
  //: plain object for an object), or `fallback` itself.
  json(key, fallback = null) {
    const raw = prefs.get(key, "");
    if (!raw) return fallback;
    let value;
    try {
      value = JSON.parse(raw);
    } catch {
      return fallback;
    }
    if (Array.isArray(fallback)) return Array.isArray(value) ? value : fallback;
    if (fallback && typeof fallback === "object") {
      return value && typeof value === "object" && !Array.isArray(value) ? value : fallback;
    }
    return value ?? fallback;
  },
  //: A finite number inside [min, max], or `fallback`: the NaN class closed.
  number(key, fallback, { min = -Infinity, max = Infinity } = {}) {
    const raw = prefs.get(key, "");
    const value = raw === "" ? NaN : Number(raw);
    if (!Number.isFinite(value)) return fallback;
    return Math.min(max, Math.max(min, value));
  },
  //: "1"/"true" and "0"/"false" as booleans; anything else is `fallback`.
  bool(key, fallback = false) {
    const raw = prefs.get(key, "");
    if (raw === "1" || raw === "true") return true;
    if (raw === "0" || raw === "false") return false;
    return fallback;
  },
  //: Store a string; a full or blocked storage is not the caller's problem.
  set(key, value) {
    try {
      const store = prefsStore();
      if (!store) return false;
      store.setItem(key, String(value));
      return true;
    } catch {
      return false;
    }
  },
  setJSON(key, value) {
    let text;
    try {
      text = JSON.stringify(value);
    } catch {
      return false;
    }
    return prefs.set(key, text);
  },
  remove(key) {
    try {
      prefsStore()?.removeItem(key);
    } catch {
      // nothing to do: it is gone either way as far as a reader can tell
    }
  },
};

//: Run each schema key's `migrate` once per version bump.
function prefsMigrate() {
  const done = prefs.json("prefs-versions", {});
  let changed = false;
  for (const [key, spec] of Object.entries(PREFS_SCHEMA)) {
    const version = spec.version || 1;
    if ((done[key] || 1) >= version) continue;
    if (typeof spec.migrate === "function" && prefs.has(key)) {
      try {
        prefs.set(key, spec.migrate(prefs.get(key)));
      } catch {
        prefs.remove(key); // an old form nothing can read is the default's
      }
    }
    done[key] = version;
    changed = true;
  }
  if (changed) prefs.setJSON("prefs-versions", done);
}
prefsMigrate();

//: **Keyboard hints in tooltips (INBOX 701).** The owner, 2026-10-06: "if
//: something has a keyboard shortcut, should they be added to the tooltips??"
//: Yes, from the one table: `DEFAULT_SHORTCUTS` in settings-wiring.js is the
//: only place a chord is written, `shortcutHint(action)` reads the binding the
//: person has now, and every tooltip that names a chord asks here, so a
//: rebound key changes its tooltip and nothing can name a key that is not
//: bound. Here, in the second file loaded, because status.js and navigation.js
//: paint tooltips before settings-wiring.js has run; the table is handed over
//: through `SHORTCUT_SOURCE` the moment it exists (and the bars repaint).
//: `tests/test_shortcut_hints.py` holds the rule.
//: Case-insensitive: Chrome's `userAgentData.platform` is "macOS", which
//: `/Mac/` alone does not match.
const SHORTCUT_MAC = /mac|iphone|ipad/i.test(
  (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "",
);
const SHORTCUT_SOURCE = { table: () => ({}) };
const SHORTCUT_MAC_SYMBOLS = {
  Ctrl: "⌘",
  Alt: "⌥",
  Shift: "⇧",
  //: Words, not arrow glyphs: a typed arrow is the lint's "glyph standing in
  //: for an icon" (`tests/test_no_glyph_icons.py`).
  ArrowLeft: "Left",
  ArrowRight: "Right",
  ArrowUp: "Up",
  ArrowDown: "Down",
  Enter: "Return",
};

//: "Ctrl+Shift+N" as the platform writes it: unchanged on Windows and Linux,
//: "⇧⌘N" on a Mac (Apple's order is Option, Shift, Command, and the
//: app's Ctrl is Command there: `matchesShortcut` treats the two as one).
function chordLabel(keys) {
  if (!keys || !SHORTCUT_MAC) return keys || "";
  const parts = keys.split("+");
  const key = parts.pop();
  const order = ["Alt", "Shift", "Ctrl"];
  const mods = order.filter((m) => parts.includes(m)).map((m) => SHORTCUT_MAC_SYMBOLS[m]);
  return mods.join("") + (SHORTCUT_MAC_SYMBOLS[key] || key);
}

//: The current binding of an action, written for this platform, or "" when
//: the action is unbound or the table is not loaded yet.
function shortcutHint(action) {
  const entry = SHORTCUT_SOURCE.table()[action];
  return entry ? chordLabel(entry.keys) : "";
}

//: "Bold" + the action's chord -> "Bold (Ctrl+B)". The one way a title gets
//: a chord appended; a lint refuses a hand-built chord in a title.
function shortcutTitle(base, action) {
  const hint = shortcutHint(action);
  return hint ? `${base} (${hint})` : base;
}

//: **The one word count** (INBOX 1495): spaced words as `wc -w` counts them,
//: and each Han or kana character as a word, so a Japanese line is never "1
//: word". Python's twin is `utilities.word_count`; every surface that says
//: "N words" goes through one of the two.
const CJK_CHARACTER = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g;
function countWords(text) {
  const value = String(text || "");
  return (value.match(CJK_CHARACTER) || []).length + (value.replace(CJK_CHARACTER, " ").match(/\S+/g) || []).length;
}

//: **The one plural helper** (sweep 1028b W14): "1 note", "3 notes", "2 categories".
//: A count in words goes through this, never `${n} notes` (tests/test_plural_helper.py).
function nounCount(n, one, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}
