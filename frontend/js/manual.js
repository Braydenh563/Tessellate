// manual.js: the manual (WORLD_CLASS_PLAN 25c, Brief 49). Every topic the
// Guide answers from (`GET /help/topics`, `help_chat.HELP_TOPICS`), on one
// page you can read through, search and print. Built from the Guide's own
// table so it cannot drift from the help: a topic written for Atlas is in the
// manual the moment it exists. Lazy: each door (Settings, Help; the Guide's
// menu; the dashboard's first steps) fetches it with `lazyScript`. The page is the
// keys-sheet recipe (DESIGN.md: a dialog head with its X, one muted line, a
// `.search-field` that filters as you type, sections of rows), opened in the
// app rather than as a second window: the desktop window hands a new window to
// the system browser, which has no session and would meet the lock.

//: Words too common to tell topics apart: "a note's Edit form" searches as
//: "note edit form". A possessive's "s" goes with them.
const MANUAL_STOP = new Set(["a", "an", "the", "s", "of", "to", "in", "on", "and", "or", "for", "its", "it", "from", "with", "by", "one"]);

function manualWords(query) {
  return String(query || "")
    .toLowerCase()
    .split(/[^a-z0-9+#]+/)
    .filter((word) => word && !MANUAL_STOP.has(word));
}

//: A topic matches when every word is in it: its title, where it is, its text
//: and the Guide's keywords for it. `tests/test_manual_parity.py` runs this
//: very function over every control the manual paths name. `things` is the
//: query read by meaning (meaning.js, Brief 94: "bin" finds the topic on the
//: trash), when the layer is in the page; the words as typed always count.
function manualMatches(topic, words, things = null) {
  const hay = `${topic.title} ${topic.path} ${topic.body} ${topic.find}`.toLowerCase();
  return words.every((word) => hay.includes(word)) || manualByName(topic, words, things);
}

//: Held by its title and keywords, the words or (meaning.js) the things they
//: name. When any topic is, only those are listed: a body names half the app.
function manualByName(topic, words, things) {
  const named = `${topic.title} ${topic.find}`.toLowerCase();
  return words.every((word) => named.includes(word)) || Boolean(things && meaningHolds(things, named));
}

//: The open manual's closer, or null: a const holder rather than a top-level
//: `let` (tests/test_global_scope_ratchet.py).
const manualOpen = { close: null };

function manualTopicEl(topic) {
  const article = document.createElement("article");
  article.className = "manual-topic";
  article.id = `manual-${topic.id}`;
  const title = document.createElement("h4");
  title.textContent = topic.title;
  article.appendChild(title);
  if (topic.path) {
    const where = document.createElement("p");
    where.className = "muted manual-where";
    where.textContent = topic.path;
    article.appendChild(where);
  }
  const body = document.createElement("p");
  body.textContent = topic.body;
  article.appendChild(body);
  //: The same `data-goto-*` button Settings, Help and the Guide's chips are:
  //: settings.js's document listener follows it; the manual closes first.
  if (topic.link && (topic.link.tab || topic.link.section)) {
    const go = document.createElement("button");
    go.type = "button";
    go.className = "linklike manual-go";
    if (topic.link.tab) go.dataset.gotoTab = topic.link.tab;
    if (topic.link.section) go.dataset.gotoSection = topic.link.section;
    if (topic.link.target) go.dataset.gotoTarget = topic.link.target;
    go.textContent = `Open ${topic.link.label}`;
    article.appendChild(go);
  }
  return article;
}

function manualBuild(listing) {
  const contents = document.createElement("nav");
  contents.className = "manual-contents";
  contents.setAttribute("aria-label", "Manual contents");
  const topics = document.createElement("div");
  topics.className = "manual-topics";
  topics.tabIndex = 0;
  const sections = [];
  listing.groups.forEach((group, index) => {
    if (!group.topics.length) return;
    const section = document.createElement("section");
    section.className = "manual-group";
    section.id = `manual-group-${index}`;
    const head = document.createElement("h3");
    head.textContent = group.title;
    section.appendChild(head);
    const rows = group.topics.map((topic) => ({ topic, el: manualTopicEl(topic) }));
    for (const row of rows) section.appendChild(row.el);
    topics.appendChild(section);
    const jump = document.createElement("button");
    jump.type = "button";
    jump.className = "manual-jump";
    jump.textContent = group.title;
    contents.appendChild(jump);
    sections.push({ section, jump, rows });
  });
  //: The contents mark the group being read, as Settings' "On this page" does.
  const follow = () => {
    let current = null;
    for (const part of sections) if (!part.section.hidden && part.section.offsetTop <= topics.scrollTop + 8) current = part;
    current = current || sections.find((part) => !part.section.hidden);
    for (const part of sections) {
      if (part === current) part.jump.setAttribute("aria-current", "location");
      else part.jump.removeAttribute("aria-current");
    }
  };
  topics.addEventListener("scroll", follow, { passive: true });
  contents.addEventListener("click", (event) => {
    const part = sections.find((one) => one.jump === event.target.closest(".manual-jump"));
    if (part) topics.scrollTop = part.section.offsetTop;
  });
  return { contents, topics, sections, follow };
}

function manualFilter(parts, query, count, empty) {
  const words = manualWords(query);
  //: meaning.js is fetched by `openManual` before the box can be typed in.
  const things = words.length ? meaningAlts(query) : null;
  const named = words.length ? meaningNamed(query) : words;
  const byName = parts.sections.some(({ rows }) => rows.some((row) => manualByName(row.topic, named, things)));
  let shown = 0;
  for (const { section, jump, rows } of parts.sections) {
    let inGroup = 0;
    for (const row of rows) {
      const hit = byName ? manualByName(row.topic, named, things) : manualMatches(row.topic, words, things);
      row.el.hidden = !hit;
      if (hit) inGroup += 1;
    }
    section.hidden = jump.hidden = !inGroup;
    shown += inGroup;
  }
  const total = parts.sections.reduce((sum, part) => sum + part.rows.length, 0);
  count.textContent = words.length
    ? `${shown} of ${total} topics match`
    : `${total} topics in ${parts.sections.length} groups`;
  empty.classList.toggle("hidden", Boolean(shown));
  parts.topics.scrollTop = 0;
  parts.follow();
}

async function openManual(topicId = "") {
  if (manualOpen.close) return;
  lazyScript("/css/manual-lazy.css");
  //: The search box's meaning layer (Brief 94), in the page before the box is.
  await lazyScript("/js/meaning.js");
  await ensureModule("quickNote");
  let listing;
  try {
    listing = await apiJson("/help/topics");
  } catch (err) {
    toast(`The manual could not be loaded: ${err.message}`, true);
    return;
  }
  if (manualOpen.close) return;
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay manual-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Manual");
  const card = document.createElement("div");
  card.className = "card modal-card manual-card";
  const returnFocus = document.activeElement;
  const onKey = (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    manualOpen.close?.();
  };
  manualOpen.close = (opts) => {
    document.removeEventListener("keydown", onKey, true);
    overlay.remove();
    manualOpen.close = null;
    if (returnFocus?.isConnected) returnFocus.focus?.();
    if (typeof overlayClosed === "function") overlayClosed("Manual", { stay: opts?.stay === true });
  };
  const head = dialogHead("Manual", () => manualOpen.close?.());
  const print = smallButton("ph:printer", "Print the manual (what is shown)", () => {
    document.body.classList.add("manual-print");
    window.addEventListener("afterprint", () => document.body.classList.remove("manual-print"), { once: true });
    window.print();
  });
  print.classList.add("icon-only", "dialog-head-btn");
  print.setAttribute("aria-label", "Print the manual");
  head.querySelector(".dialog-head-actions").prepend(print);
  const about = document.createElement("p");
  about.className = "muted manual-about";
  about.textContent = "Every topic Atlas answers from, in one place: search it, or read it through.";
  const field = document.createElement("div");
  field.className = "search-field";
  const glyph = document.createElement("i");
  glyph.className = "ph ph-magnifying-glass search-field-icon";
  glyph.setAttribute("aria-hidden", "true");
  const search = document.createElement("input");
  search.type = "search";
  search.id = "manual-search";
  search.className = "search-field-input";
  search.autocomplete = "off";
  search.placeholder = "Search the manual";
  search.setAttribute("aria-label", "Search the manual");
  field.append(glyph, search);
  const count = document.createElement("p");
  count.className = "muted manual-count";
  count.setAttribute("aria-live", "polite");
  const parts = manualBuild(listing);
  const empty = document.createElement("p");
  empty.className = "muted empty-line manual-empty hidden";
  empty.textContent = "Nothing in the manual matches. Try fewer or different words.";
  parts.topics.prepend(empty);
  const body = document.createElement("div");
  body.className = "manual-body";
  body.append(parts.contents, parts.topics);
  card.append(head, about, field, count, body);
  card.addEventListener("click", (event) => {
    if (event.target.closest("[data-goto-tab], [data-goto-section]")) manualOpen.close?.({ stay: true });
  });
  search.addEventListener("input", () => manualFilter(parts, search.value, count, empty));
  manualFilter(parts, "", count, empty);
  overlay.appendChild(card);
  wireBackdropClose(overlay, () => manualOpen.close?.());
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(overlay);
  recordTabVisit("Manual");
  const target = topicId && document.getElementById(`manual-${topicId}`);
  if (target) {
    parts.topics.scrollTop = target.offsetTop;
    target.classList.add("manual-lit");
  }
  search.focus();
}
