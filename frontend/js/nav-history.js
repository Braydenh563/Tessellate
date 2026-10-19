// nav-history.js: the rows of the status bar's back/forward list (INBOX 654),
// moved out of navigation.js into a lazy bundle (`LAZY_MODULES.navHistory`,
// with nav-history-lazy.css) so the richer rows cost the boot nothing: the
// list is opened by a press, and `openNavHistoryMenu` fetches this first.
//
//: **A row names the place, not the entry text.** The owner, with a
//: screenshot: "the nav history popup doesnt have md or image etc
//: rendering". The row was `entryLabel(entry)`, whose note branch was the
//: note's whole opening, flattened: "Notes: Girl with bell image
//: WallpaperEngineOverride_random_1.png", with repeats (Library: Files,
//: Images, Images). A row is now four things: an icon for its kind (note,
//: document, board, map, tab), the title as plain text (`notePreviewText`,
//: what the note cards and the sort use, so markdown is gone; an image-only
//: note is titled by its caption, or "Image"), a small thumbnail when the
//: note opens with a picture (`noteRowImage`, the dashboard rows' helper,
//: lazy-loaded from the URL the note already holds, so nothing new is
//: fetched), and the tab or sub-tab as a muted second line.
//:
//: History itself is not deduped: Back and Forward walk the exact stack.
//: Only the *list* folds consecutive rows that read the same.
const NAV_HISTORY_SHOWN = 12;

//: A caption that is a file name ("WallpaperEngineOverride_random_1.png", or
//: a path) is not words about the picture, so the title falls back to "Image".
function navHistoryCaption(alt) {
  const text = String(alt ?? "").trim();
  return text && !/[_/\\]|\.[A-Za-z0-9]{2,5}$/.test(text) ? text : "";
}

//: A note's title as one plain line, the way the note cards read it: the
//: heading the backend extracted, else the first non-blank line, run through
//: `flattenNoteMarkdown` and `notePreviewText`. A note whose first line is
//: only a picture is titled by its caption, or "Image". A private note never
//: shows its words anywhere a list does.
function navHistoryNoteTitle(entry) {
  if (entry.is_private) return "Private note";
  const first = stripFrontmatter(entry.content || "").split("\n").map((line) => line.trim()).find(Boolean) || "";
  const line = entry.title || first;
  const lone = /^(?:#{1,6}\s+)?!\[([^\]\n]{0,200})\]\([^)\n]{1,500}\)$/.exec(line);
  if (lone) return navHistoryCaption(lone[1]) || "Image";
  const plain = notePreviewText(flattenNoteMarkdown(line)).replace(/^[#>\s]+/, "").trim();
  return plain ? clipText(plain, 60) : noteRowImage(entry) ? "Image" : "Empty note";
}

//: A board or document title, plain: a name someone typed, which may still
//: carry the `# ` the title field was filled from.
function navHistoryPlain(text, fallback) {
  const plain = notePreviewText(flattenNoteMarkdown(text || "")).replace(/^[#>\s]+/, "").trim();
  return plain ? clipText(plain, 60) : fallback;
}

//: The tab's own icon, read from its button so a renamed icon follows.
function navHistoryTabIcon(tab) {
  const own = { settings: "gear", documents: "file-text", manual: "book-open-text", statistics: "chart-bar" }[tab];
  if (own) return own;
  const mark = document.querySelector(`#tab-bar button[data-tab="${tab}"] .tab-icon`);
  return ([...(mark?.classList || [])].find((name) => name.startsWith("ph-")) || "ph-squares-four").slice(3);
}

//: One entry as a row: `{ kind, icon, title, sub, image, key }`. `key` is what
//: two rows must share to be one row.
function navHistoryRow(entry) {
  const tab = tabLabel(entry.tab);
  const [, prefix = "", id = ""] = /^(note|doc|board|focus|conv):(.*)$/.exec(entry.section || "") || [];
  const named = historyTitles.get(entry.section);
  let row;
  if (prefix === "note" || prefix === "focus") {
    const note = allEntries.find((e) => String(e.id) === id);
    const image = note && !note.is_private ? noteRowImage(note) : null;
    row = {
      kind: "note",
      icon: prefix === "focus" ? "graph" : "note",
      title: note ? navHistoryNoteTitle(note) : navHistoryPlain(named, "A note"),
      sub: tab,
      image,
    };
  } else if (prefix === "doc") {
    row = { kind: "document", icon: "file-text", title: navHistoryPlain(named, "A document"), sub: tab, image: null };
  } else if (prefix === "board") {
    const board = mapBoardById(Number(id)) || mapBoardById(id);
    const isMap = !!board && board.type !== "board";
    row = {
      kind: isMap ? "map" : "board",
      icon: isMap ? "tree-structure" : "squares-four",
      title: navHistoryPlain(board?.title || named, isMap ? "A map" : "A board"),
      sub: tab,
      image: null,
    };
  } else if (prefix === "conv") {
    row = { kind: "chat", icon: "chat-circle", title: navHistoryPlain(named, "A chat"), sub: tab, image: null };
  } else {
    //: A sub-tab names itself ("Library: Images"): the sub-tab is the title and
    //: the tab the muted line. A bare tab is its own title.
    const label = entryLabel(entry);
    const name = label.startsWith(`${tab}: `) ? label.slice(tab.length + 2) : "";
    row = { kind: "tab", icon: navHistoryTabIcon(entry.tab), title: name || tab, sub: name ? tab : "", image: null };
  }
  row.key = [row.kind, row.title, row.sub, row.image?.url || ""].join("|");
  return row;
}

//: The stack, newest first, with runs of identical rows folded into one. A
//: folded row stands for the newest entry of its run (`index`; `lowest` is the
//: oldest), so a run holding the current entry is the current row. At most
//: `shown` rows; `older` is how many stack entries lie beyond them.
function navHistoryGroups(stack, rowOf = navHistoryRow, shown = NAV_HISTORY_SHOWN) {
  const groups = [];
  let last = null;
  for (let i = stack.length - 1; i >= 0; i--) {
    const row = rowOf(stack[i]);
    if (last && last.row.key === row.key) {
      last.lowest = i;
      continue;
    }
    if (groups.length === shown) return { groups, older: i + 1 };
    last = { row, index: i, lowest: i };
    groups.push(last);
  }
  return { groups, older: 0 };
}

function navHistoryItem(group, current) {
  const { row } = group;
  const item = document.createElement(current ? "div" : "button");
  if (!current) item.type = "button";
  item.className = `nav-history-item${current ? " nav-history-current" : ""}`;
  item.setAttribute("role", "menuitem");
  item.setAttribute("aria-label", row.sub ? `${row.title}, ${row.sub}` : row.title);
  const kind = document.createElement("i");
  kind.className = `ph ph-${row.icon} nav-history-kind`;
  kind.setAttribute("aria-hidden", "true");
  item.appendChild(kind);
  if (row.image) {
    //: Lazy and from the URL the note already holds (the dashboard rows' own
    //: thumbnail): no request is made until the row is scrolled near. A
    //: picture that has gone is dropped, not drawn as a torn page.
    const thumb = document.createElement("img");
    thumb.className = "nav-history-thumb";
    thumb.alt = "";
    thumb.loading = "lazy";
    thumb.addEventListener("error", () => thumb.remove());
    thumb.src = mediaSrc(row.image.url);
    item.appendChild(thumb);
  }
  const text = document.createElement("span");
  text.className = "nav-history-text";
  const title = document.createElement("span");
  title.className = "nav-history-title";
  title.textContent = row.title;
  text.appendChild(title);
  if (row.sub) {
    const sub = document.createElement("span");
    sub.className = "nav-history-sub";
    sub.textContent = row.sub;
    text.appendChild(sub);
  }
  item.appendChild(text);
  if (current) {
    const pin = document.createElement("i");
    pin.className = "ph ph-map-pin nav-history-pin";
    pin.setAttribute("aria-hidden", "true");
    item.appendChild(pin);
    item.title = "You're here";
    //: Focusable by the arrows only, so a history of one (the page you are
    //: on) still has a row for ArrowDown to land on.
    item.tabIndex = -1;
    item.setAttribute("aria-current", "page");
  } else {
    item.addEventListener("click", () => {
      closeNavHistoryMenu();
      goToTabHistory(group.index);
    });
    item.addEventListener("keydown", (event) => {
      if (event.key === "Delete" || event.key === "Backspace") navHistoryForget(group, event);
    });
  }
  if (current) return item;
  //: **A row can be taken off** (the owner, 2026-10-10: "no way to clear the
  //: destination history or delete individual records??"): an X beside it,
  //: shown while the row is pointed at or focused (the notification row's
  //: remove cross), or Delete on the focused row. Beside the row, not in it:
  //: a button inside a button is not a button.
  const wrap = document.createElement("div");
  wrap.className = "nav-history-row";
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "ghost small icon-only nav-history-remove";
  remove.tabIndex = -1;
  remove.title = "Remove from this list";
  remove.setAttribute("aria-label", `Remove ${row.title} from this list`);
  setLabel(remove, "ph:x");
  remove.addEventListener("click", (event) => navHistoryForget(group, event));
  wrap.append(item, remove);
  return wrap;
}

//: Out of the list and out of Back and Forward: the run the row folds goes
//: from the stack, and the place you are stays. The browser's own history
//: cannot be edited, so after this the in-app Back and Forward walk the
//: stack themselves rather than through `history.go` (`tabHistory.edited`,
//: router.js `routerGo`), whose steps would no longer line up.
function navHistoryForget(group, event) {
  event?.preventDefault();
  //: The row is about to be redrawn, so this press must not reach the
  //: document's click-away (settings-wiring.js), which would read a detached
  //: target as a press outside the list.
  event?.stopPropagation();
  const count = group.index - group.lowest + 1;
  tabHistory.stack.splice(group.lowest, count);
  if (tabHistory.index > group.index) tabHistory.index -= count;
  navHistoryEdited();
  announce("Removed from the list.");
}

function navHistoryClear(event) {
  event?.stopPropagation();
  const here = tabHistory.stack[tabHistory.index];
  tabHistory.stack = here ? [here] : [];
  tabHistory.index = here ? 0 : -1;
  navHistoryEdited();
  announce("History cleared.");
}

function navHistoryEdited() {
  tabHistory.edited = true;
  renderNavHistoryMenu();
  paintTabHistory();
  $("status-nav-history-menu").querySelector("button")?.focus({ preventScroll: true });
}

function renderNavHistoryMenu() {
  const menu = $("status-nav-history-menu");
  if (!menu) return;
  menu.replaceChildren();
  if (!tabHistory.stack.length) {
    const empty = document.createElement("div");
    empty.className = "muted nav-history-empty";
    empty.textContent = "Nowhere visited yet this session.";
    menu.appendChild(empty);
    return;
  }
  //: Asked for directly: "instead of squishing it, just make it scrollable
  //: and/or cap the history stored". Both: the stack stays at TAB_HISTORY_CAP
  //: so Back/Forward can walk a long way, and the list draws the last dozen
  //: rows (a jump list is for the places you were just at; past that you are
  //: reading a log). `max-height`/`overflow-y: auto` in 02-chat-graph.css keep
  //: the rest scrollable rather than clipped.
  const { groups, older } = navHistoryGroups(tabHistory.stack);
  for (const group of groups) {
    const current = group.lowest <= tabHistory.index && tabHistory.index <= group.index;
    menu.appendChild(navHistoryItem(group, current));
  }
  //: Say so rather than silently truncating: a jump list that quietly forgets
  //: where you were is worse than one that admits its own limit.
  //: **One footer row** (INBOX 845, the owner: "can you redesign ... this
  //: 'clear this list' button??"): the count of older steps on the left and
  //: the clear action on the right, a quiet text action, muted until it is
  //: pointed at, no icon and no fill. It was a bordered, tinted button with a
  //: trash can on a row of its own, the loudest thing in the list.
  const foot = document.createElement("div");
  foot.className = "nav-history-foot";
  if (older > 0) {
    const more = document.createElement("span");
    more.className = "muted text-xs nav-history-more";
    more.textContent = `${older} older ${older === 1 ? "step" : "steps"} not shown`;
    foot.appendChild(more);
  }
  if (tabHistory.stack.length > 1) {
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "nav-history-clear";
    clear.setAttribute("role", "menuitem");
    clear.textContent = "Clear this list";
    clear.title = "Forget every place but this one";
    clear.addEventListener("click", navHistoryClear);
    foot.appendChild(clear);
  }
  if (foot.childElementCount) menu.appendChild(foot);
}
