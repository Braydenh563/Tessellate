// settings-find.js: finding your way about inside Settings (INBOX 444).
//
// Loaded on the first open of Settings (`LAZY_MODULES.settingsUi`, app.js), not
// at boot, so none of this is in the gzip budget `test_static_compression.py`
// counts. Everything here is called from settings.js behind a `typeof` guard,
// so a page that never loaded this file still has the nav, the section filter
// and the arrow keys.
//
// Two things, both measured against a pane that is 4,700px long at 1440x900
// with nothing to say where you are in it (scratchpad/ui-sweeps/settingsia.js):
//
// 1. **A setting is found, not only the section that mentions it.** The nav
//    search already hid the sections whose text did not contain the word.
//    Typing "similarity" then left one section and a person reading it for
//    the field. The results list below the search field names each matching
//    setting (a group head or a control's label) with the section and group
//    it is in, and a press opens the section, scrolls to the setting and
//    rings it the way a catalogue row's deep link does (`flashRevealed`).
//
// 2. **A long section has an index.** A strip of the section's own group
//    heads, sticky at the top of the pane, the one you are in marked from
//    `aria-current` (DESIGN.md, "A list that says where you are"). It exists
//    only where it earns its place: four group heads or more and a pane at
//    least one and a half windows tall.

//: The elements a person would call "a setting": a group head, or the label of
//: a control. The outermost match wins (a `label.setting-check` contains its
//: own `span`), and a label inside a help popover, the nav or a hidden group is
//: not one.
const SETTING_ROW_SELECTOR = "h3, h4, label, .setting-check, .check-row, .checkbox-label, legend, .setting-label, #help-topics summary";

//: A row's visible words: its text without the helper copy beside it.
function settingRowText(el) {
  const clone = el.cloneNode(true);
  for (const extra of clone.querySelectorAll("small, .muted, .help-body, .chip, button, select, input, textarea, .fold-help-slot, .status")) {
    extra.remove();
  }
  return (clone.textContent || "").replace(/\s+/g, " ").trim();
}

//: Every findable setting in the Settings panes, read live from the DOM (the
//: panes are filled by JS after their first paint, so an index built at start
//: would be searching empty panes) and skipping what a person cannot see:
//: a pane's own hidden state does not count, a hidden group inside it does.
function settingRows() {
  //: Asked before the first query, so the first word typed is read by meaning.
  meaningAsk();
  const rows = [];
  for (const pane of document.querySelectorAll("#settings-modal .settings-section")) {
    const name = pane.id.slice("settings-".length);
    const nav = document.querySelector(`#settings-nav [data-section="${name}"]`);
    const sectionLabel = nav ? nav.textContent.trim() : name;
    for (const el of pane.querySelectorAll(SETTING_ROW_SELECTOR)) {
      if (el.closest(".help-body, .settings-pane-title, [aria-hidden='true'], .skeleton")) continue;
      //: Outermost only: a label inside a `.setting-check` is the same row.
      const outer = el.parentElement?.closest(SETTING_ROW_SELECTOR);
      if (outer && pane.contains(outer) && !outer.matches("h3, h4")) continue;
      const hiddenBy = el.closest(".hidden");
      if (hiddenBy && hiddenBy !== pane && pane.contains(hiddenBy)) continue;
      const text = settingRowText(el);
      //: A switch's own words can run long ("Load the search model when the
      //: app starts (off: ...)"); it is still a setting, where a long run of
      //: words with no control in it is a paragraph.
      if (text.length < 3 || (text.length > 110 && !el.querySelector("input, select, textarea"))) continue;
      const group = el.closest(".settings-group, details.settings-fold");
      const head = el.matches("h3, h4") ? null : group?.querySelector("h3, h4, summary h3");
      //: A help topic says which group of topics it is in (INBOX 448).
      const where = head ? head.textContent.replace(/\s+/g, " ").trim() : el.closest("[data-help-group]")?.dataset.helpGroup || "";
      //: `data-keys` and `data-find`: a help topic's keywords and text, so it is found by
      //: the words a person types, not only by its title.
      //: The row's whole text too, its helper copy included: a setting is
      //: found by what it does ("battery"), not only by its label.
      const haystack = `${text} ${el.textContent || ""} ${el.getAttribute("title") || ""} ${el.querySelector("input, select, textarea")?.getAttribute("aria-label") || ""} ${el.dataset.keys || ""} ${el.dataset.find || ""} ${el.dataset.synonyms || ""}`.toLowerCase();
      rows.push({ section: name, sectionLabel, where, text, haystack, keys: el.dataset.keys || "", synonyms: (el.dataset.synonyms || "").toLowerCase().split(/\s+/).filter(Boolean), el, isHead: el.matches("h3, h4") });
    }
  }
  return rows;
}

//: Matching settings for a typed query: every thing it names must appear, a row that
//: starts with the word or has it at a word start ranks above one that merely
//: contains it, and a group head above a control. Capped, because a list of
//: forty is the section filter over again.
//: **Words that mean one thing** (CHAT_PLAN section 2, Brief 94): "night",
//: "dark" and "theme" find the same setting, "chnage pasword" finds the
//: password. The rule is meaning.js's (`meaningAlts`, in this bundle); the
//: rows' own words are its vocabulary, so a slip of a label reads as it.
let settingVocabCache = null;
function settingVocab(rows) {
  if (rows || !settingVocabCache) {
    settingVocabCache = new Set();
    for (const row of rows || settingRows()) {
      for (const w of meaningWords(`${row.text} ${row.sectionLabel} ${row.keys}`)) settingVocabCache.add(w);
    }
  }
  return settingVocabCache;
}

//: What a query asks for, as one list of words-meaning-the-same per thing
//: named (`meaningAlts`); filterSettings (settings.js) asks it for the nav.
function settingQueryAlts(query) {
  return meaningAlts(query, settingVocab());
}

//: A query typed before the meaning tables landed is read again with them.
document.addEventListener("meaning-ready", () => {
  const box = $("settings-search");
  if (box?.value) filterSettings(box.value);
  const help = $("help-search");
  if (help?.value) helpApplySearch(help.value);
});

//: A Guide topic is a row of the Help pane: its entries carry keywords, but a
//: topic with none, and the group heads above them, are the pane's too (the
//: "Boards and maps" head ranked as a setting before the feature it names).
function settingRowIsTopic(row) {
  return Boolean(row.keys) || row.section === "help";
}

function findSettings(query, limit = 8) {
  const words = meaningNamed(query);
  if (!words.length) return [];
  const rows = settingRows();
  const alts = meaningAlts(query, settingVocab(rows));
  //: Every thing named, or, when no row holds them all, all but one of two
  //: or more ("what the ai remembers about me" is a memory question first).
  //: A help topic is held by meaning in its title and keywords only: its
  //: body names half the app. The words as typed still reach the body.
  const said = (row) => (row.keys ? `${row.text} ${row.keys}` : row.haystack);
  const plain = (row) => words.every((w) => row.haystack.includes(w));
  const pick = (miss) => rows.filter((row) => meaningMissing(alts, said(row)) <= miss);
  let found = pick(0);
  if (!found.length && alts.length > 1) found = pick(1);
  //: Within half the nearest row's closeness ("trash" is the bin, not every
  //: row that says "remove", the fifth word of the group).
  const near = new Map(found.map((row) => [row, meaningCloseness(alts, said(row))]));
  const best = Math.max(0, ...near.values());
  found = found.filter((row) => near.get(row) >= best / 2);
  found = found.concat(rows.filter((row) => !found.includes(row) && plain(row)));
  const scored = [];
  for (const row of found) {
    const lower = row.text.toLowerCase();
    let score = row.isHead ? 1 : 0;
    for (const w of words) {
      if (lower.startsWith(w)) score += 3;
      else if (lower.includes(` ${w}`)) score += 2;
      else if (lower.includes(w)) score += 1;
    }
    //: A row whose own name holds a thing ranks above one that holds it only
    //: in its helper copy, and the thing's own name above another word for it.
    score += 4 * meaningCloseness(alts, lower);
    //: Among help topics, one whose keywords hold the words as typed
    //: outranks one whose text merely contains them somewhere ("suggested
    //: downloads" is the model topic's phrase, and only scattered words in the
    //: editor's). Settings rows have no keywords, and are listed first anyway.
    const phrase = words.join(" ");
    if (row.keys.includes(phrase)) score += 3;
    else if (row.haystack.includes(phrase)) score += 1;
    //: `data-synonyms` on a setting is the word people use for it ("phone"
    //: for Other devices). A whole-word hit there outranks a query that only
    //: sits inside another word ("phone" in "Microphone"). Not `data-keys`,
    //: which would file the row among the help topics.
    if (words.some((w) => row.synonyms.includes(w))) score += 5;
    scored.push({ row, score });
  }
  scored.sort((a, b) => b.score - a.score);
  //: One line per text and section: "Models" is a head and also the first
  //: word of a label, and the same words twice is not two settings.
  const seen = new Set();
  const settings = [];
  const topics = [];
  for (const { row } of scored) {
    const key = `${row.section}|${row.text.toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    (settingRowIsTopic(row) ? topics : settings).push(row);
  }
  //: **Settings first, then help topics** (INBOX 448): "password" is a
  //: question about the password settings before it is one about the help
  //: entry on passwords, so a topic never outranks a setting. Two places are
  //: kept for topics when both match, so a word that names a setting still
  //: shows where its help is.
  const room = topics.length ? Math.max(limit - 2, limit - topics.length) : limit;
  const out = settings.slice(0, room);
  return out.concat(topics.slice(0, limit - out.length));
}

//: Open the section and bring the setting into view. `flashRevealed` scrolls
//: only when it is not already in the window and draws the same ring every
//: catalogue deep link draws.
function openSettingRow(row) {
  showSettingsSection(row.section);
  requestAnimationFrame(() => {
    const el = row.el;
    if (!el.isConnected) return;
    for (let fold = el.closest("details"); fold; fold = fold.parentElement?.closest("details")) {
      fold.open = true;
    }
    if (!el.getClientRects().length) return;
    flashRevealed(el);
    //: The row's control, not its words (OPEN, a11y: "Accent colour" landed
    //: on its DIV at both widths): a `.setting-label` stands beside its
    //: control inside `.setting-row`, and a control can be a button group
    //: (the swatches), whose chosen button is the one to land on. A head
    //: (h3, h4, legend) names a group and keeps the focus itself.
    const FIELD = "input:not([type=hidden]), select, textarea";
    const pick = (root) => root?.querySelector?.(FIELD) ||
      root?.querySelector?.('[aria-checked="true"], [aria-pressed="true"], button:not([disabled])');
    const control = el.matches("label") ? el.control || el.querySelector(FIELD)
      : el.querySelector?.(FIELD) || (el.matches(".setting-label") ? pick(el.closest(".setting-row")) : null);
    if (control && control.getClientRects().length) {
      (typeof focusSelect === "function" && control.tagName === "SELECT" ? focusSelect : (c) => c.focus({ preventScroll: true }))(control);
    } else {
      el.tabIndex = -1;
      el.focus({ preventScroll: true });
    }
  });
}

//: Draw the results under the search field. Returns how many there were.
function settingResultItem(row) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "settings-result";
  const name = document.createElement("span");
  name.className = "settings-result-name";
  name.textContent = row.text;
  const where = document.createElement("span");
  where.className = "settings-result-where";
  where.textContent = row.where && row.where !== row.text ? `${row.sectionLabel} · ${row.where}` : row.sectionLabel;
  button.append(name, where);
  button.addEventListener("click", () => openSettingRow(row));
  item.appendChild(button);
  return item;
}

function renderSettingResults(query) {
  const list = $("settings-results");
  if (!list) return 0;
  list.replaceChildren();
  const found = query.trim().length >= 2 ? findSettings(query) : [];
  for (const row of found) list.appendChild(settingResultItem(row));
  list.classList.toggle("hidden", !found.length);
  settingNearAdd(query, found);
  return found.length;
}

//: **Close in meaning** (Brief 94): with an embedding model on, up to three
//: settings nearest the words by meaning that the words themselves did not
//: reach, under their own head, once the server has answered and only if the
//: box still says the same.
function settingNearAdd(query, found) {
  if (query.trim().length < 3) return;
  const rows = settingRows().filter((row) => !row.keys);
  meaningNear(query, rows.map((row) => `${row.text} (${row.sectionLabel})`)).then((picked) => {
    const list = $("settings-results");
    if (!list || $("settings-search")?.value !== query) return;
    const listed = new Set(found.map((row) => `${row.section}|${row.text}`));
    const more = picked.map((i) => rows[i]).filter((row) => row && !listed.has(`${row.section}|${row.text}`)).slice(0, 3);
    if (!more.length) return;
    const head = document.createElement("li");
    head.className = "settings-result-head muted text-sm";
    head.setAttribute("role", "presentation");
    head.textContent = "Close in meaning";
    list.appendChild(head);
    for (const row of more) list.appendChild(settingResultItem(row));
    list.classList.remove("hidden");
  });
}

//: Arrow keys inside the results, and from the search field into them.
function settingResultsKey(event) {
  const buttons = [...document.querySelectorAll("#settings-results .settings-result")];
  if (!buttons.length) return false;
  const at = buttons.indexOf(document.activeElement);
  if (event.key === "ArrowDown") {
    buttons[Math.min(buttons.length - 1, at + 1)].focus();
    return true;
  }
  if (event.key === "ArrowUp") {
    if (at <= 0) $("settings-search")?.focus();
    else buttons[at - 1].focus();
    return true;
  }
  return false;
}

// --- the index of one section: its groups, nested in the sidebar (INBOX 622) -------
//
// The owner, of the strip this replaced: "in settings idk if this navigation
// is the right way to go about it". It was a row of the pane's group heads
// in the pane's dock that scrolled sideways, with a scrollbar and the last
// label clipped (Tools it can use). The groups are the sidebar's second level
// now, under the pane they belong to, as VS Code and Linear draw settings: a
// press scrolls the pane to the group, and the group you are reading is
// marked as you scroll. On a phone the sidebar is the jump list, which gains
// the same groups under its pane's option.

const settingsIndexScrollers = new WeakSet();
let settingsIndexWatch = null;

//: The heads an index would list: the pane's group heads in order, not the
//: pane's own title, not the ones in a popover or a hidden group.
function settingsIndexHeads(pane) {
  const heads = [];
  const title = settingsPaneTitleHead(pane);
  for (const h of pane.querySelectorAll("h3")) {
    if (h.closest(".help-body, .settings-pane-title")) continue;
    if (!h.getClientRects().length) continue;
    const label = (h.dataset.indexLabel || h.textContent).replace(/\s+/g, " ").trim();
    if (!label || (title && h === title.querySelector("h3"))) continue;
    heads.push({ el: h, label });
  }
  return heads;
}

//: The pane's own title: a `.settings-pane-title`, or a `.help-head` only
//: when it opens the pane. A `.help-head` further down is a group's head
//: (Tasks ends with "Quit Tessellate" as one), and anchoring the strip after
//: it put the strip at the bottom of the pane (INBOX 541).
function settingsPaneTitleHead(pane) {
  const title = pane.querySelector(":scope > .settings-pane-title");
  if (title) return title;
  const first = [...pane.children].find((c) => c.getClientRects().length);
  return first?.matches(".help-head, .dock") ? first : null;
}

//: A head stops just under the pane's sticky dock (INBOX 599).
function settingsIndexOffset(pane) {
  const bar = pane && settingsPaneTitleHead(pane);
  return (bar?.matches(".dock") ? bar.getBoundingClientRect().height : 0) + 8;
}

//: The sidebar's group list, when it belongs to this pane.
function settingsIndexList(name) {
  const list = document.querySelector("#settings-nav .settings-nav-groups");
  return list && list.dataset.section === name ? list : null;
}

//: Where the scroller should stop for a head: its top just under the sticky
//: dock. The box's own `scrollTop`, never `scrollIntoView`, which walks every
//: scrollable ancestor (DESIGN.md, the outline recipe).
function settingsIndexGo(name, head) {
  const scroller = settingsScroller(name);
  if (!scroller) return;
  const delta = head.getBoundingClientRect().top - scroller.getBoundingClientRect().top - settingsIndexOffset($(`settings-${name}`));
  //: **The head clicked is the head marked** (INBOX 459, the owner: on
  //: Personas the strip "only goes on the first or last one"). Heads near a
  //: short pane's end can never reach the line, so the scroll position
  //: alone marked the last; the choice holds until the reader scrolls by
  //: hand (wheel, touch, keys), which `_indexUnpin` listens for.
  scroller._indexPinned = head;
  if (!scroller._indexUnpin) {
    scroller._indexUnpin = () => { scroller._indexPinned = null; };
    for (const type of ["wheel", "touchstart", "keydown"]) scroller.addEventListener(type, scroller._indexUnpin, { passive: true });
  }
  scroller.scrollTo({ top: scroller.scrollTop + delta, behavior: typeof reducedMotionWanted === "function" && reducedMotionWanted() ? "auto" : "smooth" });
  settingsIndexMark(name);
  head.tabIndex = -1;
  head.focus({ preventScroll: true });
}

//: **The sidebar follows the page** (INBOX 680, the owner: should it "scroll a
//: little to show the quick access in page sections"). When the marked link
//: changes it is scrolled into the sidebar's view, to the nearest edge rather
//: than the centre, with the sidebar's own `scrollTop` (never `scrollIntoView`,
//: which walks every ancestor, and never `focus`). It leaves the sidebar alone
//: while the pointer is over it or the person scrolled it in the last 600ms;
//: its own scroll is not counted as theirs. Smooth only under the motion
//: switches (reduced motion, Interface animations).
function settingsNavFollow(link) {
  //: Found once: the marker changes many times in one scroll of Help, and
  //: each walk asked a computed style of every ancestor (12-15ms of a
  //: 40-step scroll).
  const box = settingsNavFollow.box?.contains(link) ? settingsNavFollow.box : (settingsNavFollow.box = nearestScrollParent(link));
  if (box === document.documentElement) return;
  if (!box._followWired) {
    box._followWired = true;
    box.addEventListener("scroll", () => {
      if (performance.now() - (box._followAt || 0) > 700) box._userScrollAt = performance.now();
    }, { passive: true });
  }
  if (box.matches(":hover") || performance.now() - (box._userScrollAt || 0) < 600) return;
  const have = box.getBoundingClientRect();
  const at = link.getBoundingClientRect();
  const pad = 8;
  const delta = at.top < have.top + pad ? at.top - have.top - pad : at.bottom > have.bottom - pad ? at.bottom - have.bottom + pad : 0;
  if (!delta) return;
  const root = document.documentElement;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches || root.dataset.motion === "reduced" || root.dataset.uiMotion === "off";
  box._followAt = performance.now();
  box.scrollTo({ top: box.scrollTop + delta, behavior: still ? "auto" : "smooth" });
}

//: Mark the head the pane is scrolled to. `aria-current="location"` is the
//: whole state; the paint is the stylesheet's.
function settingsIndexMark(name) {
  const nav = settingsIndexList(name);
  const scroller = settingsScroller(name);
  if (!nav || !scroller) return;
  const line = scroller.getBoundingClientRect().top + settingsIndexOffset($(`settings-${name}`)) + 24;
  let current = 0;
  const links = [...nav.querySelectorAll(".settings-nav-group")];
  //: Heads are in page order: the first one below the line ends the look.
  for (const [i, link] of links.entries()) {
    const head = link._head;
    if (!head?.isConnected) continue;
    if (head.getBoundingClientRect().top > line) break;
    current = i;
  }
  const pinned = links.findIndex((link) => scroller._indexPinned && link._head === scroller._indexPinned);
  if (pinned >= 0) current = pinned;
  //: At the very bottom the last head may never reach the line.
  else if (scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 2) current = links.length - 1;
  //: The sidebar is followed before any attribute moves: the follow measures,
  //: and a measure after the write was a second style and layout pass in the
  //: frame (`settingsNavFollow` 17-26ms of a 40-step scroll of Help).
  const link = links[current];
  if (link && link.getAttribute("aria-current") !== "location") {
    settingsNavFollow(link);
    for (const other of links) if (other !== link) other.removeAttribute("aria-current");
    link.setAttribute("aria-current", "location");
  }
  //: The phone's jump list follows the group you are reading.
  const jump = document.getElementById("settings-jump");
  const value = `${name}#${current}`;
  if (jump && jump.value !== value && jump.querySelector(`option[value="${CSS.escape(value)}"]`)) {
    jump.value = value;
    echoSettingsPaneTitle(jump);
  }
}

//: Take the groups out of the sidebar and the jump list.
function settingsIndexClear() {
  document.querySelector("#settings-nav .settings-nav-groups")?.remove();
  document.querySelectorAll(".settings-jump option[data-group]").forEach((o) => o.remove());
}

//: The jump list's group options (a native `<select>` on a phone, built by
//: phone-shell.js): indented under their pane's option, `pane#index`. The
//: jump list's own handler clicks `button[data-section="pane#index"]`, which
//: matches nothing, so a group is this file's to answer.
function settingsIndexJump(name, heads) {
  const jump = document.querySelector(".settings-jump");
  const option = jump?.querySelector(`option[value="${CSS.escape(name)}"]`);
  if (!option) return;
  let at = option;
  heads.forEach(({ label }, i) => {
    const row = document.createElement("option");
    row.value = `${name}#${i}`;
    row.textContent = ` ${label}`;
    row.dataset.group = "";
    at.after(row);
    at = row;
  });
  if (jump._groupsWired) return;
  jump._groupsWired = true;
  jump.addEventListener("change", () => {
    const [pane, at] = jump.value.split("#");
    const link = settingsIndexList(pane)?.querySelectorAll(".settings-nav-group")[Number(at)];
    if (link) settingsIndexGo(pane, link._head);
  });
}

//: Build, refresh or remove the index for the section on screen. Cheap when
//: nothing changed (a signature of the heads), so it can run on every change
//: to the pane without looping on its own insertion.
function settingsIndexBuild(name) {
  const pane = $(`settings-${name}`);
  if (!pane || pane.classList.contains("hidden")) return;
  const scroller = settingsScroller(name);
  const existing = settingsIndexList(name);
  const heads = settingsIndexHeads(pane);
  //: **Every section with three or more groups has one** (INBOX 541, the
  //: owner: "some dont have any at all"). It used to need four heads and a
  //: pane half again as tall as the window, so whether a section had a strip
  //: changed with the window's height.
  if (heads.length < 3 || !scroller) {
    settingsIndexClear();
    return;
  }
  const signature = heads.map((h) => h.label).join("|");
  if (existing && existing.dataset.signature === signature) {
    existing.querySelectorAll(".settings-nav-group").forEach((link, i) => {
      link._head = heads[i].el;
    });
    settingsIndexMark(name);
    return;
  }
  settingsIndexClear();
  const list = document.createElement("div");
  list.className = "settings-nav-groups";
  list.setAttribute("role", "group");
  list.setAttribute("aria-label", "In this section");
  list.dataset.section = name;
  list.dataset.signature = signature;
  //: **"On this page", short unless asked** (INBOX 698): the head names the block
  //: and carries the toggle for the rest of the sections, which is remembered
  //: per device. Collapsed, only the link being read shows (the stylesheet).
  let showAll = false;
  showAll = prefs.get("settings-nav-sections") === "all";
  const head = document.createElement("div");
  head.className = "settings-nav-groups-head";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "linklike";
  const paint = () => {
    list.classList.toggle("is-open", showAll);
    toggle.setAttribute("aria-expanded", String(showAll));
    toggle.textContent = showAll ? "Show fewer" : `Show all ${nounCount(heads.length, "section")}`;
  };
  toggle.addEventListener("click", () => {
    showAll = !showAll;
    prefs.set("settings-nav-sections", showAll ? "all" : "current");
    paint();
    settingsIndexMark(name);
    const current = list.querySelector('[aria-current="location"]');
    if (current) settingsNavFollow(current);
  });
  head.append(Object.assign(document.createElement("span"), { textContent: "On this page" }), toggle);
  list.appendChild(head);
  paint();
  for (const { el, label } of heads) {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "settings-nav-group";
    link.textContent = label;
    link._head = el;
    link.addEventListener("click", () => settingsIndexGo(name, link._head));
    list.appendChild(link);
  }
  //: Under the pane's own link: the sidebar's second level.
  $("settings-nav")?.querySelector(`button[data-section="${CSS.escape(name)}"]`)?.after(list);
  glideStrip(list); // its rail slides as you scroll the pane (shell-reminders.js)
  settingsIndexJump(name, heads);
  if (scroller && !settingsIndexScrollers.has(scroller)) {
    settingsIndexScrollers.add(scroller);
    let queued = false;
    scroller.addEventListener(
      "scroll",
      () => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
          queued = false;
          settingsIndexMark(currentSettingsSection);
        });
      },
      { passive: true }
    );
  }
  settingsIndexMark(name);
}

//: Called when a section opens: build now, again once its async content has
//: arrived, and keep it current while the pane changes.
function settingsIndexWatchSection(name) {
  //: Each row's changed marker and reset (WORLD_CLASS_PLAN 25f), a file of its own.
  lazyScript("/js/settings-rows.js").then((ok) => ok && settingRowsWatch(name));
  settingsIndexWatch?.disconnect();
  settingsIndexWatch = null;
  const pane = $(`settings-${name}`);
  if (!pane) return;
  const build = () => {
    if (currentSettingsSection === name) settingsIndexBuild(name);
  };
  requestAnimationFrame(build);
  setTimeout(build, 700);
  if (pane.querySelectorAll("h3").length < 3) return;
  let timer = null;
  settingsIndexWatch = new MutationObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(build, 250);
  });
  settingsIndexWatch.observe(pane, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "open"] });
}

// --- the help topics (INBOX 448 (1)) ----------------------------------------------
//
// Settings, Help lists every entry the Guide reads (`GET /help/topics`, from
// `help_chat.HELP_TOPICS`), grouped, instead of thirteen hand-copied topics
// that had drifted from it. Each group is a head and a `.help-accordion`, the
// recipe the page already used; a topic is a `details` whose summary carries
// the entry's keywords in `data-keys` and its text in `data-find`, so the
// search above finds "percentage"
// or "bookmarks" as a row and a press opens that topic. Fetched once per page
// load; a failed fetch is tried again on the next open.

let helpTopicsLoad = null;

function helpTopicLink(link) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "linklike";
  if (link.tab) button.dataset.gotoTab = link.tab;
  if (link.section) button.dataset.gotoSection = link.section;
  if (link.target) button.dataset.gotoTarget = link.target;
  button.textContent = `Open ${link.label}`;
  //: The manual's own topic opens the manual itself, not Settings, Help (owner, 2026-10-19).
  if (link.manual) button.addEventListener("click", () => lazyScript("/js/manual.js").then((ok) => ok && openManual()));
  return button;
}

// --- emphasis (INBOX 520) -----------------------------------------------------------
//
// The topics are the Guide's facts, so they stay plain text; the page decorates
// its own copy: a hotkey is a `kbd`, a place (`Settings, Models`, `Library tab,
// Contents`) a `strong`, a control or a quoted phrase a `code` chip. Names come
// from the page's own nav and tabs, so a rename cannot leave this behind.

const HELP_NAME_ESCAPE = /[.*+?^${}()|[\]\\]/g;
const HELP_NAMED_KEYS = String.raw`Ctrl|Alt|Shift|Enter|Esc|Tab|Space|Delete|F\d{1,2}|Up|Down|Left|Right|Home|End|PageUp|PageDown`;
const HELP_KEYS = [
  String.raw`(?:Ctrl|Cmd|Alt|Shift|Option)(?:\/(?:Cmd|Ctrl))?(?:\+(?:${HELP_NAMED_KEYS}|[A-Za-z0-9](?![A-Za-z])|[\[\]\\/.,=-]))+`,
  String.raw`\b(?:Escape|Esc|Enter|Tab|Space|F\d{1,2}|Delete(?= (?:removes|deletes)))\b`,
  //: "Press m then r": the two letters are keys.
  String.raw`(?<=\b[Pp]ress )[a-z](?= then [a-z](?![\w']))|(?<=\b[Pp]ress [a-z] then )[a-z](?![\w']| letter)`,
].join("|");
const HELP_PLACE = String.raw`[A-Z][A-Za-z]*(?: (?:and|&) [A-Z][A-Za-z]*)?(?![A-Za-z]| [a-z])`;
let helpEmphasisKey = "";
let helpEmphasisRx = null;
let helpNameLists = null;

function helpAlternation(names) {
  const list = names.map((n) => n.replace(HELP_NAME_ESCAPE, "\\$&")).sort((a, b) => b.length - a.length);
  return list.length ? list.join("|") : "(?!)";
}

//: `text` as [tag, piece] pairs: tag is "kbd", "strong", "code" or "" (plain).
function helpEmphasis(text, places, tabs) {
  const key = `${places.join("|")}#${tabs.join("|")}`;
  if (key !== helpEmphasisKey) {
    helpEmphasisKey = key;
    const place = `Settings(?:, then|,| ->| →) (?:${helpAlternation(places)})(?![A-Za-z])|Settings(?: ->| →) [A-Z][a-z]+`;
    const tab = `(?:${helpAlternation(tabs)})(?: tab(?:, ${HELP_PLACE})?|, ${HELP_PLACE})`;
    const control = String.raw`(?<=\b[Pp]ress )([A-Z][A-Za-z]*(?: [a-z]+){0,2})(?=[:,.;)]| to\b| and\b| or\b)`;
    helpEmphasisRx = new RegExp(`(${HELP_KEYS})|(${place}|${tab})|${control}|"([^"\\n]{2,60})"`, "g");
  }
  const out = [];
  let at = 0;
  for (const m of text.matchAll(helpEmphasisRx)) {
    if (m.index > at) out.push(["", text.slice(at, m.index)]);
    out.push([m[1] ? "kbd" : m[2] ? "strong" : "code", m[1] || m[2] || m[3] || m[4]]);
    at = m.index + m[0].length;
  }
  if (at < text.length || !out.length) out.push(["", text.slice(at)]);
  return out;
}

//: The text in `parent`: emphasis as elements, the typed words marked inside.
function helpFill(parent, text, rx) {
  helpNameLists ||= [
    [...document.querySelectorAll("#settings-nav button[data-section]")].map((b) => b.textContent.trim()),
    [...document.querySelectorAll("#tab-bar [data-tab] .tab-label")].map((b) => b.textContent.trim()),
  ];
  for (const [tag, piece] of helpEmphasis(text, ...helpNameLists)) {
    const host = tag ? document.createElement(tag) : parent;
    helpMarks(host, piece, rx);
    if (tag) parent.append(host);
  }
}

//: Text into `parent`, the typed words wrapped in `<mark>` (DOM nodes only).
function helpMarks(parent, text, rx) {
  let at = 0;
  for (const m of rx ? text.matchAll(rx) : []) {
    parent.append(text.slice(at, m.index));
    const mark = document.createElement("mark");
    mark.className = "help-hit";
    mark.textContent = m[0];
    parent.append(mark);
    at = m.index + m[0].length;
  }
  parent.append(text.slice(at));
}

//: Draw (or redraw, with the words marked) a topic's title, text and place.
function helpTopicPaint(details, rx) {
  const topic = details._topic;
  const [summary, body, where] = details.children;
  summary.replaceChildren();
  helpMarks(summary, topic.title, rx);
  body.replaceChildren();
  helpFill(body, topic.body, rx);
  const path = where?.firstChild;
  if (topic.path && path) {
    path.replaceChildren("Where: ");
    helpFill(path, topic.path, rx);
  }
}

function helpTopicRow(topic) {
  const details = document.createElement("details");
  details.dataset.topic = topic.id;
  details._topic = topic;
  const summary = document.createElement("summary");
  summary.dataset.keys = topic.find.toLowerCase();
  summary.dataset.find = topic.body.toLowerCase();
  details._help = [topic.title, topic.find, topic.body, topic.path].join(" ").toLowerCase();
  details._named = `${topic.title} ${topic.find}`.toLowerCase();
  details.append(summary, document.createElement("p"));
  //: A link to Help from inside Help goes nowhere.
  const link = topic.id === "manual" ? { manual: true, label: "the manual" } : topic.link && topic.link.section !== "help" ? topic.link : null;
  if (topic.path || link) {
    const where = document.createElement("p");
    where.className = "help-topic-links muted";
    where.appendChild(document.createElement("span"));
    if (topic.path && link) where.append(" · ");
    if (link) where.appendChild(helpTopicLink(link));
    details.appendChild(where);
  }
  helpTopicPaint(details, null);
  return details;
}

// --- search (INBOX 520) -------------------------------------------------------------

//: The typed words that name something (meaning.js: "how do I" and "my"
//: name nothing); a topic must hold every one.
function helpQueryTerms(query) {
  return meaningNamed(query);
}

//: How a topic holds the query: above 1 by its name and keywords (`named`),
//: the words or the things they name (meaning.js, Brief 94: "trash" is "Undo
//: and the bin"), more the nearer the words typed; 1 by its body's words
//: only; 0 not at all.
function helpMatches(terms, text, things = null, named = text) {
  const whole = terms.every((term) => named.includes(term));
  if (whole || (things && meaningHolds(things, named))) return 2 + (whole ? 1 : 0) + (things ? meaningCloseness(things, named) : 0);
  return terms.every((term) => text.includes(term)) ? 1 : 0;
}

//: A topic held by name must come within this share of the nearest one (the
//: Guide's runner-up rule, help_chat.py `_RUNNER_UP_SHARE`): "trash" is the
//: bin's topic, not every topic whose keywords say "remove".
const HELP_RUNNER_UP = 0.85;

let helpOpenBefore = null;

//: Hide what does not match, open what does with the words marked, hide a
//: group head whose topics are all gone, and say so when nothing is left.
//: Clearing puts every fold back as it was.
function helpApplySearch(query) {
  const box = $("help-topics");
  if (!box) return;
  const terms = helpQueryTerms(query);
  const searching = terms.length > 0;
  const things = searching ? meaningAlts(query) : null;
  const escaped = terms.map((t) => t.replace(HELP_NAME_ESCAPE, "\\$&")).sort((a, b) => b.length - a.length);
  const rx = searching ? new RegExp(escaped.join("|"), "gi") : null;
  if (searching && !helpOpenBefore) helpOpenBefore = new Map([...box.querySelectorAll("details")].map((d) => [d, d.open]));
  let shown = 0;
  let total = 0;
  //: Topics that hold the query by name, when any do; the bodies only when
  //: none does: a body names half the app, so "the little guy in the
  //: corner" listed a dozen topics ahead of the companion's own.
  const lists = [...box.querySelectorAll(".help-accordion")];
  const tiers = new Map();
  for (const list of lists) for (const details of list.children) tiers.set(details, helpMatches(terms, details._help, things, details._named));
  const best = Math.max(0, ...tiers.values());
  const floor = best >= 2 ? Math.max(2, best * HELP_RUNNER_UP) : 1;
  for (const list of lists) {
    let any = false;
    //: The best match first within its group while searching, and the
    //: written order back once the box is cleared (OPEN 1109: a topic held by
    //: its name sat below weaker ones, help top-3 38/60 against Settings' 58/60).
    const order = [...list.children];
    order.forEach((details, at) => { if (details._helpAt === undefined) details._helpAt = at; });
    order.sort((a, b) => (searching ? tiers.get(b) - tiers.get(a) : 0) || a._helpAt - b._helpAt);
    if (order.some((details, at) => details !== list.children[at])) list.append(...order);
    for (const details of list.children) {
      total += 1;
      const hit = !searching || tiers.get(details) >= floor;
      details.classList.toggle("hidden", !hit);
      if (!hit) continue;
      any = true;
      shown += 1;
      details.open = searching || (helpOpenBefore?.get(details) ?? details.open);
      helpTopicPaint(details, rx);
    }
    list.classList.toggle("hidden", !any);
    list.previousElementSibling?.classList.toggle("hidden", !any);
  }
  //: The tours and the Atlas row are sections of the page too.
  let others = 0;
  for (const group of document.querySelectorAll("#settings-help > .settings-group")) {
    const hit = helpMatches(terms, group.textContent.toLowerCase(), things) > 0;
    group.classList.toggle("hidden", !hit);
    if (hit) others += 1;
  }
  if (!searching) helpOpenBefore = null;
  $("help-empty")?.classList.toggle("hidden", !searching || shown + others > 0);
  const status = $("help-search-status");
  if (status) {
    status.textContent = searching ? `${shown} of ${nounCount(total, "topic")}` : "";
    status.classList.toggle("hidden", !searching);
  }
}

function helpSearchBind() {
  const input = $("help-search");
  if (!input || input._bound) return;
  input._bound = true;
  //: The manual (manual.js, lazy): the same topics as one page.
  $("help-open-manual")?.addEventListener("click", () => lazyScript("/js/manual.js").then((ok) => ok && openManual()));
  input.addEventListener("input", () => helpApplySearch(input.value));
  input.addEventListener("keydown", (e) => {
    //: Escape clears the query before it closes the window.
    if (e.key !== "Escape" || !input.value) return;
    e.stopPropagation();
    e.preventDefault();
    input.value = "";
    helpApplySearch("");
  });
}

//: **Settings, Help, Credits**: every library the app is built on, from
//: frontend/credits.json (scripts/build_credits.py writes it from
//: docs/THIRD_PARTY.md; tests/test_credits.py holds the two equal). Drawn the
//: first time the fold opens: a group head per part, then a row per library
//: with its licence and a link to where it came from.
let creditsLoad = null;
function renderCredits() {
  const fold = $("credits-fold");
  const box = $("credits-list");
  if (!fold || !box || fold.dataset.wired) return;
  fold.dataset.wired = "1";
  const draw = () => {
    if (!fold.open || creditsLoad) return;
    creditsLoad = api("/credits.json", { silent: true })
      .then((answer) => (answer.ok ? answer.json() : Promise.reject(new Error(String(answer.status)))))
      .then((data) => {
        const parts = [];
        for (const group of data.groups || []) {
          const head = document.createElement("h4");
          head.className = "setting-subhead";
          head.textContent = group.title;
          const list = document.createElement("ul");
          list.className = "credits-rows";
          for (const row of group.rows) {
            const item = document.createElement("li");
            const name = document.createElement("a");
            name.href = row.source;
            name.target = "_blank";
            name.rel = "noopener noreferrer";
            name.textContent = row.name;
            const licence = document.createElement("span");
            licence.className = "muted";
            licence.textContent = row.licence;
            item.append(name, licence);
            list.append(item);
          }
          parts.push(head, list);
        }
        box.replaceChildren(...parts);
        box.removeAttribute("aria-busy");
      })
      .catch(() => {
        creditsLoad = null;
        const line = document.createElement("p");
        line.className = "muted";
        line.textContent = "The credits did not load. The full list is in docs/THIRD_PARTY.md.";
        box.replaceChildren(line);
        box.removeAttribute("aria-busy");
      });
  };
  fold.addEventListener("toggle", draw);
  draw();
}

function renderHelpTopics() {
  helpSearchBind();
  const box = $("help-topics");
  if (!box || helpTopicsLoad) return helpTopicsLoad;
  helpTopicsLoad = apiJson("/help/topics")
    .then((data) => {
      const parts = [];
      for (const group of data.groups || []) {
        const head = document.createElement("h3");
        head.textContent = group.title;
        const list = document.createElement("div");
        list.className = "help-accordion";
        list.dataset.helpGroup = group.title;
        for (const topic of group.topics) list.appendChild(helpTopicRow(topic));
        parts.push(head, list);
      }
      box.replaceChildren(...parts);
      box.removeAttribute("aria-busy");
      if ($("help-search")?.value) helpApplySearch($("help-search").value);
      if (typeof currentSettingsSection !== "undefined" && currentSettingsSection === "help") settingsIndexBuild("help");
    })
    .catch(() => {
      helpTopicsLoad = null;
      const line = document.createElement("p");
      line.className = "muted";
      line.textContent = "The help topics did not load. Ask Atlas below, or reopen Settings to try again.";
      box.replaceChildren(line);
      box.removeAttribute("aria-busy");
    });
  return helpTopicsLoad;
}
