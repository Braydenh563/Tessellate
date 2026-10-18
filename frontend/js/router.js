// router.js: every view has an address (WORLD_CLASS_PLAN 22.1 item 1).
//
// Each view gets a hash (`#/notes/12`, `#/chat/45`, `#/docs/7`,
// `#/library/images`, `#/settings/appearance`), and this file keeps three
// things in step: navigation.js's back stack (the source of truth for what a
// step is and how to go back to one, `openHistoryEntry`), the address bar (a
// new view is pushed, a refinement replaces) and the window title.
//
// `popstate` drives navigation: the in-app Back and Forward call `history.go`
// and the browser's answer opens the entry its state names. A hash with no
// entry behind it (a pasted link, a bookmark) opens as a fresh visit; one that
// is not a route (a heading anchor, `#intro`) is left alone. Nothing runs at
// load but the listener and the address the page was opened with, which the
// boot opens after the unlock (`routerRestore`, app.js).

const ROUTE_TABS = { dashboard: "dashboard", notes: "notes", chat: "chat", docs: "documents", library: "library", graph: "graph", timeline: "timeline", reminders: "reminders", settings: "settings" };
const ROUTE_NOTES_SECTIONS = ["capture", "writing-room", "ask", "questions"];
//: The Library's sub-tabs by the word the address uses. Images and Files are
//: one view (`library-view-media`) in two kinds, so their sections carry the
//: kind; "All" is the view whose id kept the old name, documents.
const ROUTE_LIBRARY = { all: "library-view-documents", documents: "library-view-docs", boards: "library-view-whiteboard", images: "library-view-media:images", files: "library-view-media:files", skills: "library-view-skills", links: "library-view-links", contents: "library-view-contents", recordings: "library-view-recordings" };

//: The things with an address of their own: the tab, the history section's
//: prefix and the path word before the id. One table for `routeHash` (a
//: history entry) and `routeHashFor` (a kind and an id), so a new kind is one row.
const ROUTE_OBJECTS = {
  note: { tab: "notes", prefix: "note:", path: "notes" },
  chat: { tab: "chat", prefix: "conv:", path: "chat" },
  document: { tab: "documents", prefix: "doc:", path: "docs" },
  board: { tab: "library", prefix: "board:", path: "library/board" },
  map: { tab: "library", prefix: "board:", path: "library/board" },
  graph: { tab: "graph", prefix: "focus:", path: "graph/focus" },
};
const ROUTE_OBJECT_LIST = Object.values(ROUTE_OBJECTS);

//: The hash for one history entry (`{tab, section}`, navigation.js).
function routeHash(entry) {
  const tab = entry && entry.tab;
  const section = entry && entry.section != null ? String(entry.section) : "";
  const object = ROUTE_OBJECT_LIST.find((row) => row.tab === tab && section.length > row.prefix.length && section.startsWith(row.prefix));
  if (object) return `#/${object.path}/${section.slice(object.prefix.length)}`;
  switch (tab) {
    case "notes":
      return ROUTE_NOTES_SECTIONS.includes(section) ? `#/notes/${section}` : "#/notes";
    case "chat":
      return "#/chat";
    case "documents":
      return "#/docs";
    case "library": {
      const word = Object.keys(ROUTE_LIBRARY).find((key) => ROUTE_LIBRARY[key] === section);
      return word ? `#/library/${word}` : "#/library";
    }
    case "graph":
      return "#/graph";
    case "settings":
      return section ? `#/settings/${section}` : "#/settings";
    default:
      return ROUTE_TABS[tab] === tab ? `#/${tab}` : "#/dashboard";
  }
}

//: One object's hash (`routeHashFor("note", 12)` is `#/notes/12`), or "" for
//: a kind with no address or an id that is not a number.
function routeHashFor(kind, id) {
  const object = ROUTE_OBJECTS[kind];
  return object && /^\d+$/.test(String(id)) ? routeHash({ tab: object.tab, section: object.prefix + id }) : "";
}

//: "Copy app link": the full address of one object, to paste into another
//: app or a note. Origin and path, never the query. True when it was copied.
async function copyObjectAddress(kind, id) {
  const hash = routeHashFor(kind, id);
  if (!hash) {
    toast("This has no address until it is saved.");
    return false;
  }
  if (!(await copyToClipboard(location.origin + location.pathname + hash))) return false;
  toast("Link copied.");
  return true;
}

//: The "Copy app link" menu row, the same in every object's menu (the wiki
//: link row, where there is one, is "Copy wiki link"). `id` may be a function,
//: for a menu built before its object is known (the open chat).
function appLinkMenuItem(kind, id) {
  return makeMenuItem("ph:link Copy app link", `Copy this ${kind}'s address to open it in the app`, () => copyObjectAddress(kind, typeof id === "function" ? id() : id));
}

//: The hash of an address that points at a view of this app (this origin and
//: page, a route the router opens), or "": a pasted app link then opens in this
//: window instead of a new tab. Only the hash is ever used as the link.
function appAddressHash(url) {
  if (!/^(?:https?:\/\/|#\/)/i.test(String(url || "").trim())) return "";
  try {
    const parsed = new URL(String(url).trim(), location.href);
    return parsed.origin === location.origin && parsed.pathname === location.pathname && routeEntry(parsed.hash) ? parsed.hash : "";
  } catch {
    return "";
  }
}

//: What an app link reads as in text: the title when the view was visited
//: (`historyTitles`), else the kind and id ("Note 12"), else the view's name.
function appAddressLabel(hash) {
  const entry = routeEntry(hash);
  const kind = entry && Object.keys(ROUTE_OBJECTS).find((key) => ROUTE_OBJECTS[key].tab === entry.tab && String(entry.section).startsWith(ROUTE_OBJECTS[key].prefix));
  if (!kind) return (entry && ROUTE_VIEW_NAMES[entry.tab]) || hash;
  const title = typeof historyTitles !== "undefined" && historyTitles.get(entry.section);
  return title || `${kind.charAt(0).toUpperCase()}${kind.slice(1)} ${entry.section.slice(ROUTE_OBJECTS[kind].prefix.length)}`;
}

//: The entry a hash names, or null when the hash is not a route (an empty
//: one, an in-page anchor, a tab that does not exist, an id that is not one).
function routeEntry(hash) {
  const match = /^#\/([a-z-]+)(?:\/(.*))?$/.exec(String(hash || ""));
  if (!match) return null;
  const tab = ROUTE_TABS[match[1]];
  if (!tab) return null;
  const rest = match[2] || "";
  const number = (text) => (/^\d+$/.test(text) ? text : null);
  if (!rest) return { tab, section: null };
  switch (tab) {
    case "notes":
      if (ROUTE_NOTES_SECTIONS.includes(rest)) return { tab, section: rest };
      return number(rest) ? { tab, section: `note:${rest}` } : null;
    case "chat":
      return number(rest) ? { tab, section: `conv:${rest}` } : null;
    case "documents":
      return number(rest) ? { tab, section: `doc:${rest}` } : null;
    case "library": {
      const board = /^board\/(\d+)$/.exec(rest);
      if (board) return { tab, section: `board:${board[1]}` };
      return ROUTE_LIBRARY[rest] ? { tab, section: ROUTE_LIBRARY[rest] } : null;
    }
    case "graph": {
      const focus = /^focus\/(\d+)$/.exec(rest);
      return focus ? { tab, section: `focus:${focus[1]}` } : null;
    }
    case "settings":
      return /^[a-z-]+$/.test(rest) ? { tab, section: rest } : null;
    default:
      return null;
  }
}

//: What the window title calls a view.
const ROUTE_VIEW_NAMES = { dashboard: "Dashboard", notes: "Notes", chat: "Chat", documents: "Documents", library: "Library", graph: "Graph", timeline: "Timeline", reminders: "Reminders", settings: "Settings" };

//: The address the page was opened with, read before anything below rewrites
//: it: the boot's own first visit (the Dashboard) replaces the address, and
//: the view that was asked for is opened after the unlock.
const routerBootHash = location.hash;
//: True while this file is opening an entry: the visits that opening makes
//: are the same view, so they replace rather than push.
let routerReplacing = false;
let routerNextId = 1;

//: The window's title for an entry: the open thing (a note, a document, a
//: conversation, a board), the view, and the app's name (`setTitleView`,
//: status.js, keeps the notification count in front of all three).
function routerPaintTitle(entry) {
  if (typeof setTitleView !== "function" || !entry) return;
  const view = ROUTE_VIEW_NAMES[entry.tab] || "";
  let item = entry.section && typeof historyTitles !== "undefined" ? historyTitles.get(entry.section) || "" : "";
  //: A sub-tab by the word its address uses (Images, Capture, Appearance).
  if (!item && entry.section) {
    const word = entry.tab === "library"
      ? Object.keys(ROUTE_LIBRARY).find((key) => ROUTE_LIBRARY[key] === entry.section)
      : entry.tab === "settings" || ROUTE_NOTES_SECTIONS.includes(entry.section) ? entry.section : "";
    if (word) item = word.charAt(0).toUpperCase() + word.slice(1).replace(/-/g, " ");
  }
  setTitleView([item, view].filter(Boolean).join(" · "));
}

//: A visit navigation.js has just recorded (`pushed`: a new entry; else the
//: entry on top was refined in place). Mirrored into the browser's history
//: with the stack entry's id, so a `popstate` can find it again.
function routerOnVisit(entry, pushed) {
  if (!entry) return;
  if (!entry.navId) entry.navId = routerNextId++;
  const hash = routeHash(entry);
  //: `depth`: how many of this app's entries sit under this one in the
  //: browser's history, so a step back never leaves the app (router-overlays.js).
  const depth = (history.state && history.state.depth) || 0;
  const url = `${location.pathname}${location.search}${hash}`;
  try {
    if (pushed && !routerReplacing && history.state && history.state.navId) history.pushState({ navId: entry.navId, depth: depth + 1 }, "", url);
    else history.replaceState({ navId: entry.navId, depth }, "", url);
  } catch {
    // A sandboxed or file: page can refuse; the in-app stack still works.
  }
  routerPaintTitle(entry);
}

//: The in-app Back and Forward, through the browser's own history, so the
//: two cannot disagree: `history.go` answers with `popstate`, below. Only
//: when the entry on screen is one this file mirrored; otherwise (a history
//: the browser does not have, a page that refused pushState) the stack walks
//: on its own, the way it did before there was a router.
function routerGo(delta) {
  const here = tabHistory.stack[tabHistory.index];
  //: `edited`: rows taken off the list (nav-history.js) put the stack and the
  //: browser's history out of step, so the stack walks on its own from then.
  if (!delta || tabHistory.edited || !here || !history.state || history.state.navId !== here.navId) return false;
  history.go(delta);
  return true;
}

//: Open a view named by an address that has no entry behind it: a pasted
//: link, a bookmark, a hash typed by hand, a reload. A fresh visit, opened by
//: the same code the history walk uses, replacing the address it came from.
async function routerOpen(entry) {
  if (!entry || typeof openHistoryEntry !== "function") return false;
  routerReplacing = true;
  try {
    await openHistoryEntry(entry);
  } finally {
    routerReplacing = false;
  }
  return true;
}

window.addEventListener("popstate", async (event) => {
  //: router-overlays.js (lazy): Back with an overlay open closes the overlay.
  if (typeof routerBackHook === "function" && routerBackHook(event)) return;
  const navId = event.state && event.state.navId;
  const index = navId ? tabHistory.stack.findIndex((entry) => entry.navId === navId) : -1;
  if (index >= 0) {
    await goToTabHistory(index, { fromBrowser: true });
    routerPaintTitle(tabHistory.stack[tabHistory.index]);
    return;
  }
  const entry = routeEntry(location.hash);
  if (entry) await routerOpen(entry);
});

//: The boot's half (app.js, once the notes are in): the view the page was
//: opened with, if it named one other than where the app starts. True when
//: it opened one, so the boot does not also reload the Dashboard over it.
async function routerRestore() {
  const entry = routeEntry(routerBootHash);
  if (!entry || (entry.tab === "dashboard" && !entry.section)) return false;
  return routerOpen(entry);
}
