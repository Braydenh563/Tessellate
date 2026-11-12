// dashboard.js: widgets, masonry, the generative art (split out of app.js).
// Everything here calls app.js globals only at run time, inside functions,
// so load order matters only the other way: app.js reaches in from its own
// functions (refreshActiveTab, switchTab, the appearance code). Two split
// hazards, both a bare top-level reference resolving before this file loads:
// the features-close wiring moved here beside its functions, and
// ai-tools.js's applyPalette calls refreshArtForTheme unguarded, which holds
// because applyAppearance now runs from settings.js's tail, after this file.
// Left in app.js: tickClocks (Reminders uses it too), the tab-bar overflow
// fade, safeMdSlice/notePreviewText/renderEmblem (shared), the Settings
// appearance and persona code, and the AI Skills page.

// --- dashboard (Wave D) -----------------------------------------------------------

let dashEditMode = false;
//: After a reorder the grid reflows under the pointer; without a pause the
//: next dragover moved the card straight back (release: "a complete mess").
let dashDragLockUntil = 0;

//: A named function rather than inline in renderDashboard's card loop: the
//: rect reads run on dragover, never in that loop, and the layout lint
//: (test_css_invalidation) reads a loop body statically.
function dashDragOverCard(e, card, dragged, grid) {
  //: **Decided by where the pointer is on the target, not by order.**
  //: The old rule moved the card on every dragover by index alone, so
  //: once the grid reflowed under the pointer the next dragover moved it
  //: back: two cards swapping places over and over. Now: before or
  //: after the target by which half of it the pointer is over (the x
  //: half on the same row, the y half otherwise), nothing when the card
  //: is already in that place, and a short pause after each move while
  //: the grid settles.
  const now = performance.now();
  if (now < dashDragLockUntil) return;
  const r = card.getBoundingClientRect();
  const d = dragged.getBoundingClientRect();
  const sameRow = Math.abs(r.top - d.top) < r.height / 2;
  const before = sameRow ? e.clientX < r.left + r.width / 2 : e.clientY < r.top + r.height / 2;
  const ref = before ? card : card.nextSibling;
  if (ref === dragged || ref === dragged.nextSibling) return;
  grid.insertBefore(dragged, ref);
  dashDragLockUntil = now + 220;
}
let dragWidget = null; // widget name being dragged

// Widget registry: name → title + async renderer that fills a body div.
// `description` is a one-line, plain-text (no ph: marker) summary shown only
// in the widget picker modal, the on-dashboard header just uses `title`.
const DASH_WIDGETS = {
  stats: { title: "ph:chart-bar Stats", description: "Note count, tags, categories and other totals at a glance.", render: renderStatsWidget },
  streak: { title: "ph:flame Streak", description: "How many days in a row you've added or edited a note.", render: renderStreakWidget },
  art: { title: "ph:palette Notebook constellation", description: "A generative starfield: one cluster per category, sized by note count.", render: renderArtWidget },
  //: The key stays `pinned`, it is a stored widget id, and renaming it would
  //: silently drop the widget off every dashboard that has it turned on. Only
  //: what a person reads changes, which is the half that was inconsistent:
  //: the sidebar and the note cards call this Favourites.
  pinned: { title: "ph:star Favourites", description: "Notes you've starred, so they're always one click away.", render: renderPinnedWidget },
  "recent-notes": { title: "ph:clock Recently added", description: "The last few notes you created, newest first.", render: renderRecentNotesWidget },
  //: WORLD_CLASS_PLAN B1's strip: the event feed (`GET /events`) had no
  //: reader. Not a second "Recently added": that one lists what you wrote,
  //: this one what *happened*, including what Atlas or a skill changed on
  //: your behalf, which is the one thing no other widget can say.
  activity: { title: "ph:pulse Recent activity", description: "What changed in your notebook lately, and whether you, Atlas or a skill changed it.", render: renderActivityWidget },
  //: WORLD_CLASS_PLAN I1's morning card over `GET /night/latest`.
  night: { title: "ph:moon-stars While you were away", description: "What Atlas worked out reading your notes on its own, with each finding to open or dismiss.", render: renderNightWidget },
  "most-used": { title: "ph:flame Most used", description: "The notes you open and ask about most often.", render: renderMostUsedWidget },
  //: WORLD_CLASS_PLAN section 17 rows 5 and 1: the owner's "most-accessed
  //: information" for this month (`GET /most-opened`, a day-by-day open log),
  //: and the filings waiting for a person (`GET /review-queue`).
  "most-opened": { title: "ph:eye Most opened this month", description: "The ten notes you opened most in the last thirty days.", render: renderMostOpenedWidget },
  review: { title: "ph:checks Filings to check", description: "Notes Atlas was unsure where to file, and notes left Uncategorised, to accept or move.", render: renderReviewWidget },
  "most-linked": { title: "ph:link Most-linked notes", description: "The notes with the most connections, the hubs of your notebook.", render: renderMostLinkedWidget },
  "top-tags": { title: "ph:tag Top tags", description: "Your most-used tags, ranked by how many notes carry them.", render: renderTopTagsWidget },
  questions: { title: "ph:chat-circle Recent questions", description: "The questions you've recently asked the notebook's chat.", render: renderQuestionsWidget },
  "on-this-day": { title: "ph:calendar-blank On this day", description: "What you wrote on this date in earlier months and years.", render: renderOnThisDayWidget },
  digest: { title: "ph:newspaper Digest", description: "Your day from the notes: what is due, open questions, what changed and quiet topics; Atlas writes the week on request.", render: renderDigestWidget },
  capture: { title: "ph:pencil-simple Quick capture", description: "The Notes tab's take-a-note bar: a note, a to-do list or a drawing, without leaving the dashboard.", render: renderQuickCaptureWidget },
  reminders: { title: "ph:alarm Reminders", description: "Upcoming and overdue reminders, soonest first.", render: renderRemindersWidget },
  focus: { title: "ph:timer Focus timer", description: "A focus timer with breaks, a chime at the end and today's minutes.", render: renderFocusTimerWidget },
  heatmap: { title: "ph:calendar-check Activity heatmap", description: "A calendar-style heatmap of note activity over the past months.", render: renderHeatmapWidget },
  "tag-cloud": { title: "ph:cloud Tag cloud", description: "All your tags sized by how often they're used.", render: renderTagCloudWidget },
  categories: { title: "ph:folders Categories", description: "Every category with its note count, click to filter.", render: renderCategoriesWidget },
  //: The key stays `random`, it is a stored widget id and renaming it would
  //: drop the widget off every dashboard that has it turned on. What it does
  //: changed (WORLD_CLASS_PLAN 15, I4): over ten notes it shows the three
  //: notes furthest out of reach, ranked by age, links and opens, with the
  //: reason on each card; under ten it still shuffles, because "the three
  //: most faded" out of five notes is the same three for ever.
  random: { title: "ph:dice-five Rediscover", description: "The notes slipping out of reach: old, unlinked and unopened, with the reason for each.", render: renderRandomNoteWidget },
  //: **Four surfaces the dashboard could not see at all.**
  //:
  //: Every widget above this line reads notes. But a notebook here is also
  //: boards, documents, and the state a note is *in*, and the dashboard is
  //: the one screen meant to answer "what is going on in here", so a feature
  //: with no widget is a feature the dashboard is blind to. Audited against
  //: the tab bar rather than brainstormed: Boards & maps, Documents, and the
  //: two things about notes that nothing surfaced (which ones still have work
  //: left in them, and which ones are stranded).
  boards: { title: "ph:squares-four Boards & maps", description: "The board or map with the most on it, drawn large at its own shape, then the next four.", render: renderBoardsWidget },
  documents: { title: "ph:file-text Recent documents", description: "The documents you last edited, newest first.", render: renderDocumentsWidget },
  //: The Library sub-tab this reads was renamed Links -> Bookmarks (INBOX
  //: 430: "links" read as note-to-note links to anyone who hadn't opened
  //: the tab), and this widget is the other half of the same fix: the
  //: dashboard could see recent notes, documents and boards already, but
  //: nothing about the one Library surface that isn't a note or a file.
  bookmarks: { title: "ph:bookmark-simple Bookmarks", description: "Your recently saved bookmarks, pinned ones first.", render: renderBookmarksWidget },
  unfinished: { title: "ph:check-square-offset Unfinished", description: "Notes with checklist items you haven't ticked off yet.", render: renderUnfinishedWidget },
  orphans: { title: "ph:link-break Loose ends", description: "How much of your notebook is connected to anything, and the oldest notes that aren't.", render: renderOrphanNotesWidget },
  //: Deliberately a doorway rather than a live reading. Every other widget
  //: here answers from data already loaded; this one's answer costs a model
  //: pass over pairs of notes, so rendering the dashboard must not start one.
  tensions: { title: "ph:scales Tensions", description: "Find where your notes contradict each other, a decision reversed, a date that moved, a view you changed.", render: renderTensionsWidget },
  //: **What a notebook can tell you that a to-do list cannot:** whether you
  //: are actually writing. Answered entirely from `allEntries`, which is
  //: already loaded, no request, no model. (Its sibling idea, what you
  //: were thinking about on this date in earlier years, turned out to
  //: already exist as `on-this-day` above under a different key; reported
  //: directly as two identical widgets in the picker, "on-this-day" kept
  //: since it was the original and removing `onthisday` here needed no
  //: layout migration: `dashLayout()` already drops any saved id that
  //: isn't in this object.)
  //: Brief 89 (statistics row 2): Screen Time's weekly report, drawn by
  //: statistics.js, which also holds the page it opens.
  week: { title: "ph:calendar-dots This week", description: "Notes made, words written and reminders done this week, against last week.", render: (body) => renderWeekWidget(body) },
  pace: { title: "ph:chart-line-up Writing pace", description: "How many words you have written each day this fortnight.", render: renderPaceWidget },
};

//: Widgets that are the wrong shape in one column, so they start in two.
//:
//: The owner: "the heatmap on the dashboard is a little small." Measured at
//: 1440x900, and it is arithmetic rather than taste: the widget column is
//: 306px, a year is 53 columns of squares, and at a 3px gap the gaps alone
//: eat 156px of the 306, leaving **2.8px per cell**. A year of activity is
//: supposed to be a shape you read at a glance and that is a texture. In a
//: full-width section the same grid gets 1408px and its cells hit the 12px
//: cap, which is the size GitHub's own is drawn at.
//:
//: Applied only when the saved layout widens *nothing*, so it is a default
//: rather than an override: the moment anyone presses "Wide" or "Narrow" on
//: any widget, their list wins and this is never consulted again.
//: The constellation starts wide (the owner's own layout, 2026-10-12); its
//: Narrow button is checked by `tests/test_dashboard_default_wide.py`.
const DASH_DEFAULT_WIDE = ["art"];

//: **What a dashboard nobody has arranged shows** (INBOX 393: "I lose trust
//: in ... applications with poor ui design"). Every widget used to be on by
//: default: measured, 23 cards on a fresh dashboard, most of them empty-state
//: sentences on a new notebook, which reads as a demo of widgets rather than
//: a place to start. A fresh layout shows these nine, in this order: what is
//: due, what is new, what is kept, a box to write in, then the work and the
//: look back. The other fourteen are one press away under Widgets. Only a
//: layout that has never been saved is affected; any saved choice wins.
const DASH_DEFAULT_SHOWN = [
  "digest", "art", "capture", "recent-notes", "reminders", "pinned",
  "documents", "boards", "heatmap", "on-this-day", "week",
];

//: Widgets added after the dashboard shipped that start switched off. The
//: owner asked for a dashboard with less on it (INBOX 270), so a new widget is
//: offered in the picker rather than appended to every existing dashboard.
//: Applied only while a saved layout has never seen the widget: once anybody
//: adds it, or saves a layout with it hidden, the saved layout decides.
const DASH_OPT_IN = ["activity", "night", "week"];

//: **The popup tools as widgets** (INBOX 1558, the owner: "cant add the timer,
//: calculator, converter, stopwatch etc"). A widget draws the tool itself, not
//: a button that opens it: the Clock and the Calculator mount into the body
//: through the popup's own build (`host`). A `POPUP_TOOLS` entry (settings-panes.js)
//: names its widget; a kind no tool names is not listed (tests/test_popup_widgets_1558.py).
{
  const POPUP_WIDGETS = {
    clock: { title: "ph:timer Clock", description: "Timers, a stopwatch and an alarm, drawn here. They keep running when you leave the page.", module: "utilities", mount: (body) => openClockPanel.inline("timer", body) },
    //: One tab each, with no strip (INBOX 1617): a Stopwatch and an Alarm of their own beside the Clock, over the same running clocks and the same reminders.
    stopwatch: { title: "ph:timer Stopwatch", description: "A stopwatch with Start, Pause, Lap and Reset, and the laps listed. It keeps running when you leave the page.", module: "utilities", mount: (body) => openClockPanel.inline("stopwatch", body, { only: true }) },
    alarm: { title: "ph:bell-ringing Alarm", description: "A time of day and a label. It is an ordinary reminder, so it rings with the reminder sound and notification and is kept.", module: "utilities", mount: (body) => openClockPanel.inline("alarm", body, { only: true }) },
    convert: { title: "ph:ruler Convert", description: "Units, currency and time zones: an amount and two units, or a time and two places, worked out here with no model.", module: "replyKit", mount: (body) => openCalculator.inline(body, "convert", { only: true }) },
    calculator: { title: "ph:calculator Calculator", description: "Sums, percentages and unit conversions, worked out here with no model.", module: "replyKit", mount: (body) => openCalculator.inline(body, "work") },
  };
  for (const [id, kind] of Object.entries(POPUP_WIDGETS)) {
    if (!POPUP_TOOLS.some((tool) => tool.widget === id)) continue;
    DASH_WIDGETS[id] = { title: kind.title, description: kind.description, render: (body) => ensureModule(kind.module).then(() => kind.mount(body)) };
    DASH_OPT_IN.push(id);
  }
}

function dashLayout() {
  const saved = (prefsCache && prefsCache.dashboard_layout) || {};
  //: Empty lists count as never arranged: the preference's own default is
  //: `{order: [], hidden: []}`, and Reset writes the same, so Reset returns to
  //: this set too.
  const fresh = !saved.order?.length && !saved.hidden?.length;
  const order = [...(fresh ? DASH_DEFAULT_SHOWN : saved.order || [])];
  const hidden = fresh
    ? Object.keys(DASH_WIDGETS).filter((n) => !DASH_DEFAULT_SHOWN.includes(n))
    : [...(saved.hidden || [])];
  for (const name of Object.keys(DASH_WIDGETS)) {
    if (!order.includes(name)) {
      order.push(name); // new widgets append
      if (DASH_OPT_IN.includes(name) && !hidden.includes(name)) hidden.push(name);
    }
  }
  // Older layouts stored this as {name: "wide"}, fold those in so a saved
  // layout still works.
  const legacyWide = Object.keys(saved.sizes || {}).filter((n) => saved.sizes[n] === "wide");
  return {
    order: order.filter((n) => DASH_WIDGETS[n]),
    hidden,
    //: `narrow` is what someone set back to one column. Without it, Narrow on
    //: the heatmap (the only default wide widget) saved an empty `wide`, which
    //: reads as "never chosen" and put the default straight back.
    wide: (saved.wide?.length
      ? saved.wide
      : (legacyWide.length ? legacyWide : DASH_DEFAULT_WIDE.filter((n) => DASH_WIDGETS[n])))
      .filter((n) => !(saved.narrow || []).includes(n)),
    narrow: [...(saved.narrow || [])],
  };
}

async function saveDashLayout(layout) {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ dashboard_layout: layout }),
  }).catch(() => prefsCache);
}

// Add/remove and wide/narrow, factored out of the inline "Edit layout" grid
// so the widget-picker modal (dash-widgets-dialog) can flip the same
// `dashboard_layout` preference instead of growing a second copy of this
// logic. Both surfaces call these, then re-render themselves.
async function toggleDashWidgetHidden(name) {
  const next = dashLayout();
  next.hidden = next.hidden.includes(name)
    ? next.hidden.filter((n) => n !== name)
    : [...next.hidden, name];
  await saveDashLayout(next);
}

async function toggleDashWidgetWide(name) {
  const next = dashLayout();
  const narrowing = next.wide.includes(name);
  next.wide = narrowing ? next.wide.filter((n) => n !== name) : [...next.wide, name];
  next.narrow = narrowing ? [...next.narrow.filter((n) => n !== name), name] : next.narrow.filter((n) => n !== name);
  await saveDashLayout(next);
}
// --- dashboard welcome banner ------------------------------------------------
// A few phrasings per time of day so the greeting feels alive. The choice is
// keyed to the day + time-block, so it changes occasionally rather than
// flickering on every re-render.
const GREETINGS = {
  morning: ["Good morning", "Morning", "Rise and shine", "A fresh start"],
  afternoon: ["Good afternoon", "Afternoon", "Hope today's going well"],
  evening: ["Good evening", "Evening", "Winding down"],
  night: ["Still up", "Working late", "Burning the midnight oil"],
};

function greetingBlock(hour) {
  if (hour < 5) return "night";
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  if (hour < 23) return "evening";
  return "night";
}

// The local fallback phrase, used until (or instead of) an AI-written one.
function fallbackGreetingPhrase(now = new Date()) {
  const options = GREETINGS[greetingBlock(now.getHours())];
  // Same greeting for a whole block on a given day, then it moves on.
  const daySlot = Math.floor(now.getTime() / 86400000) + now.getHours();
  return options[daySlot % options.length];
}

//: A name longer than this is cut at a word with an ellipsis in the greeting (X25).
const GREETING_NAME_MAX = 40;

// The name always comes from preferences, never from the model, so it can't
// be mangled or hallucinated, and editing it takes effect immediately. The
// terminal mark goes on last so the result reads as a proper sentence:
// "Rise and shine" + ", Sam" + "." → "Rise and shine, Sam." A cached "!" from
// before the server stopped sending one reads as a full stop (INBOX 472).
function withDisplayName(phrase, punctuation = ".", appendName = true) {
  const full = ((prefsCache && prefsCache.display_name) || "").trim();
  const name = clipText(full, GREETING_NAME_MAX);
  const mark = punctuation === "?" ? "?" : ".";
  // Also sentence-cased here, so an older cached greeting written by the model
  // in lowercase corrects itself on the next render.
  const opener = phrase ? phrase.charAt(0).toUpperCase() + phrase.slice(1) : phrase;
  // Don't append when the server says the greeting already handles the name, 
  // either the model wove it in, or this one is deliberately nameless. The
  // text check is a belt-and-braces guard against a stale cache.
  const already =
    !appendName ||
    (full && new RegExp(`\\b${full.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(opener));
  if (!name || already) return `${opener}${mark}`;
  return `${opener}, ${name}${mark}`;
}

function dashboardGreetingText(now = new Date()) {
  //: Name-free until the server says this greeting takes it (`ai/address.py`).
  return withDisplayName(fallbackGreetingPhrase(now), ".", false);
}

// A cached AI greeting, refreshed once per time-block per day so it changes
// occasionally rather than on every render (and doesn't hammer the model).
function greetingCacheSlot(now = new Date()) {
  // Refreshed hourly, so the banner keeps changing through the day instead of
  // repeating the same line for a whole morning. The name is part of the slot
  // too: renaming yourself in Settings invalidates the cached greeting so the
  // AI writes a fresh one addressed to the new name.
  const name = ((prefsCache && prefsCache.display_name) || "").trim();
  //: And how much of a notebook there is (none, a few, many): a line composed
  //: for an empty one ("Your first note is waiting") was kept for the hour
  //: after three notes were written (blind test 2026-10-31).
  const notes = typeof allEntries === "undefined" ? 0 : Math.min(allEntries.length, 3);
  return `${now.toDateString()}|${now.getHours()}|${name}|${notes}`;
}

function cachedGreetingPhrase(now = new Date()) {
  try {
    const cached = prefs.json("greetingCache", null);
    if (cached && cached.slot === greetingCacheSlot(now) && cached.phrase) {
      return {
        phrase: cached.phrase,
        punctuation: cached.punctuation || ".",
        appendName: cached.appendName !== false,
      };
    }
  } catch {
    /* a corrupt cache just means we fetch a fresh one */
  }
  return null;
}

// Ask the AI for this block's greeting. Silent by design: any failure simply
// leaves the handwritten fallback on screen. `forced` skips the cache check, 
// used by the Settings "Regenerate" button (asked for directly) so a click
// gets a genuinely new line instead of the one already cached for this hour.
async function refreshAiGreeting(forced = false) {
  const now = new Date();
  if (!forced && cachedGreetingPhrase(now)) return; // still fresh for this block
  const block = greetingBlock(now.getHours());
  const body = await apiJson(`/insights/greeting?block=${block}`, { silent: true }).catch(
    () => null
  );
  const phrase = body && body.greeting;
  if (!phrase) return false;
  const punctuation = (body && body.punctuation) || ".";
  const appendName = !(body && body.append_name === false);
  prefs.set(
    "greetingCache",
    JSON.stringify({ slot: greetingCacheSlot(now), phrase, punctuation, appendName })
  );
  const el = $("dash-greeting");
  if (el) el.textContent = withDisplayName(phrase, punctuation, appendName);
  return true;
}

//: The stopper `startMinuteTicker` (shell-reminders.js) hands back, not a timer id: a
//: chained timeout has a new id every tick, so an id could not cancel it.
let dashClockTimer = null;

function stopDashClock() {
  if (dashClockTimer) dashClockTimer();
  dashClockTimer = null;
}

function startDashClock() {
  stopDashClock();
  // Nothing to tick for while nobody can see it. The repaint on return is
  // what makes stopping safe: resuming on the next tick would leave the time
  // it stopped at on screen for up to a second, which on a clock is the one
  // place a person notices.
  if (document.hidden) return;
  //: One wake a minute, on the minute, rather than sixty: this paints HH:MM,
  //: so 59 of every 60 runs wrote the string already on screen. See
  //: `startMinuteTicker` in shell-reminders.js for why it is a wall-clock-aligned
  //: timeout chain and not a 60,000 ms interval (INBOX 266, item 7).
  dashClockTimer = startMinuteTicker(paintDashClock);
}

document.addEventListener("visibilitychange", () => {
  // Only while the dashboard is actually drawn: `paintDashClock` returns at
  // once when its two elements are not in the page, but a ticker started
  // on every tab would still be a ticker.
  if (!$("dash-clock-time")) return;
  if (document.hidden) {
    stopDashClock();
    return;
  }
  paintDashClock();
  startDashClock();
});

function paintDashClock() {
  const timeEl = $("dash-clock-time");
  const dateEl = $("dash-clock-date");
  if (!timeEl || !dateEl) return;
  const now = new Date();
  timeEl.textContent = now.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    ...clockOptions(),
  });
  dateEl.textContent = now.toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  //: The sub line rotates (INBOX 1300): a new draw once its bucket has passed.
  if (dashLine.bucket && dashLineDraw() !== dashLine.bucket) renderDashSubmessage().catch(() => {});
}

// A short line about the notebook, note count, plus whatever's most
// worth surfacing right now (due reminders, then a capture streak).
//: **One `/insights/stats` per moment, not one per widget.** Seven widgets
//: each asked for it on their own, so a boot fetched it five times at about
//: 200 ms each (measured 2026-09-13). The first caller's promise is shared
//: for two seconds; a widget that renders later than that asks afresh.
//:
//: The body called *itself* when this was written, which no test could see and
//: no probe reported as an error: the recursion blew the stack on the first
//: call, every one of the seven call sites has a `.catch`, and the widgets that
//: read stats simply drew their empty state. What gave it away was the boot
//: fetch log, where `/insights/stats` did not appear at all, having gone from
//: five requests to none rather than to one.
let dashStatsInflight = null;
let dashStatsAt = 0;
function fetchDashStats() {
  const now = Date.now();
  if (dashStatsInflight && now - dashStatsAt < 2000) return dashStatsInflight;
  dashStatsAt = now;
  //: A deadline (INBOX 513, the owner: Stats, Streak and the constellation
  //: "stuck loading"): three widgets wait on this one request, so a request
  //: that never answered left all three on "Loading…" for good. It fails
  //: instead, each card offers Retry, and the next call asks again.
  const pending = apiJson("/insights/stats", { timeoutMs: 15000 });
  dashStatsInflight = pending;
  pending.catch(() => {
    if (dashStatsInflight === pending) dashStatsInflight = null;
  });
  return pending;
}

//: **One `/graph` per moment, not one per widget**, the same shape and the
//: same reason as `fetchDashStats` above. Three widgets read the edge list
//: (most-linked, orphan notes, tensions) and all three render in the same
//: pass, so the `cacheMs` two of them passed could never help: a read cache
//: is only a cache once a response has come back, and these three requests
//: were in flight together. Measured at boot: three `/graph` builds, which is
//: the most expensive endpoint on the dashboard's list.
let dashGraphInflight = null;
let dashGraphAt = 0;
function fetchDashGraph() {
  const now = Date.now();
  if (dashGraphInflight && now - dashGraphAt < 2000) return dashGraphInflight;
  dashGraphAt = now;
  //: `slim=1`, the map's own read (GRAPH_PLAN, a slimmer node): the widgets
  //: read only each link's two ends, and one shape means one cached build
  //: after a change serves the dashboard and the map alike.
  dashGraphInflight = apiJson("/graph?slim=1", { silent: true });
  return dashGraphInflight;
}

//: **One reminder walk per moment.** Three places on this tab want every
//: reminder (the greeting line's due count, the stat tile, and the reminders
//: widget), and all three render in the same pass, so a cold start walked
//: `/reminders` three times over (WORLD_CLASS_PLAN A2). To the end of the
//: list, not the first page: `/reminders` is `due_at` ascending, so a first
//: page of old, ticked-off rows would hide everything upcoming
//: (`archive/agent-remaining/list-paging.md`).
let dashRemindersInflight = null;
let dashRemindersAt = 0;
function dashReminders() {
  const now = Date.now();
  if (dashRemindersInflight && now - dashRemindersAt < 2000) return dashRemindersInflight;
  dashRemindersAt = now;
  dashRemindersInflight = apiPagedList("/reminders", 200);
  return dashRemindersInflight;
}

//: The notebook, for the four widgets that want the whole of it.
//:
//: `entriesEverLoaded`, not `allEntries.length`: an empty list is an answer,
//: and reading it as "not loaded yet" meant a notebook with nothing in it
//: fetched the whole of `/entries` again per widget per render, boot included,
//: to be told the same thing (WORLD_CLASS_PLAN A2). A new notebook is exactly
//: the one where the empty state is what the person is looking at.
//:
//: Before the notes list has its first page, the store's `notes` slice is
//: waited for (F12) rather than `/entries` fetched a second time: at boot the
//: dashboard and the notes list both asked for the same thousand rows. A load
//: that never lands (`appState.when`'s timeout gives null) still falls back.
async function dashEntries() {
  if (entriesEverLoaded) return allEntries;
  const notes = await appState.when("notes", 8000);
  return notes || apiJson("/entries", { cacheMs: 4000 });
}

//: **The sub line is composed and rotates** (INBOX 1300, the owner: "Maybe the
//: sub text below the greeting can rotate or change around a bit??"). The
//: draw is the three-minute bucket the clock is in, so a repaint inside it
//: keeps the words and the next bucket (a later visit, or the minute tick
//: noticing) takes another; it swaps text with no animation, so reduced
//: motion needs nothing. `dashTodayLine` is in dash-day.js (lazy).
const DASH_LINE_MS = 180000;
const dashLine = { bucket: 0 };
const dashLineDraw = () => Math.floor(Date.now() / DASH_LINE_MS);

async function renderDashSubmessage() {
  const el = $("dash-submessage");
  if (!el) return;
  dashLine.bucket = dashLineDraw();
  const [stats, reminders, patterns, composed] = await Promise.all([
    fetchDashStats().catch(() => null),
    // To the end: `/reminders` is `due_at` ascending, so a first page of
    // old, ticked-off rows would hide everything upcoming from this count
    // (`archive/agent-remaining/list-paging.md`); `dashReminders` shares
    // the one fetch across the widgets that need it.
    dashReminders().catch(() => []),
    //: The Patterns line (CHAT_PLAN decision 32), its short form here and
    //: the measured sentence on hover; Tidy shows it whole.
    apiJson("/insights/patterns", { silent: true }).catch(() => null),
    dashTodayLine(dashLine.bucket).catch(() => ""),
  ]);
  const bits = [];
  if (composed) bits.push(["notes", composed]);
  else if (stats) {
    const n = stats.total_entries;
    bits.push(["notes", n === 0 ? "No notes yet" : `You have ${nounCount(n, "note")}`]);
  }
  //: One count for every surface that says it (ai/due_summary.py, audit 2 G3).
  const counted = dashGlanceFacts({ reminders }).find((f) => f.id === "due");
  if (counted.today + counted.overdue) bits.push(["reminders", counted.say]);
  else if (counted.later) bits.push(["reminders", `${nounCount(counted.later, "reminder")} coming up`]);
  if (stats && stats.per_day) {
    const streak = dashStreak(stats.per_day);
    if (streak > 1) bits.push(["streak", `${streak}-day capture streak`]);
    //: Atlas celebrates a streak of three days or more, once a day at most
    //: (atlas.js, `atlasStreak`), and the companion cheers once when it grows
    //: (avatars.js). Here since INBOX 436 took the stat strip that used to
    //: carry both calls off the first screen: this line reads the same figure.
    atlasStreak(streak);
    nameMarkBuddyStreak(streak, stats.total_entries);
  }
  //: A different pattern each day, not always the first (the owner, 2026-10-26:
  //: "I keep seeing this one pattern and nothing else").
  const found = patterns?.patterns || [];
  const pattern = found[Math.floor(Date.now() / 86400000) % (found.length || 1)];
  if (pattern) bits.push(["patterns", "Pattern: ", pattern.text]);
  //: One span per fact, its separator inside it, so a view can fold one fact
  //: away whole: the Focused hero's glance says what is due (INBOX 675), and
  //: hides the reminders fact here rather than saying it twice.
  el.replaceChildren(
    ...bits.map(([kind, text, whole], i) => {
      const bit = document.createElement("span");
      bit.className = "dash-sub-bit";
      bit.dataset.bit = kind;
      bit.textContent = i ? ` · ${text}` : text;
      if (whole) bit.title = whole;
      //: B84: its words open its notes; its ⋯ asks if it is right (dash-day.js).
      if (kind === "patterns") dashPatternBit(bit, pattern);
      return bit;
    })
  );
}

function renderDashboardGreeting() {
  const el = $("dash-greeting");
  if (!el) return;
  // Paint instantly from the cache (or the handwritten fallback), then let an
  // AI-written phrase replace it in the background if one arrives.
  const cached = cachedGreetingPhrase();
  el.textContent = cached
    ? withDisplayName(cached.phrase, cached.punctuation, cached.appendName)
    : dashboardGreetingText();
  refreshAiGreeting().catch(() => {});
  renderNameNudge(el);
  // Drawn here rather than at startup: renderEmblem reads the current accent,
  // so it has to be redrawn when the dashboard repaints after a theme change.
  // It also can't be sized while the tab is display:none, p5 measures zero , 
  // which is why this sits in the dashboard's own render and not in init.
  paintDashEmblem();
  paintDashClock();
  // One ticking clock, however many times the dashboard re-renders, none at
  // all while the tab is hidden, and one wake a minute while it is not. It
  // paints HH:MM, so a hidden tab was waking the process once a second to
  // write the string that was already there, for as long as the app stayed
  // open (WORLD_CLASS_PLAN section 10, F6: "0 timers while hidden"), and a
  // visible one was doing the same 59 times out of 60.
  startDashClock();
  renderDashSubmessage().catch(() => {});
  renderDashGlance().catch(() => {});
}

//: **The Focused hero's glance** (INBOX 675, the owner, with a screenshot at
//: about 2000px: "can you improve the dashboard hero section on the focused
//: view??"). The banner was a greeting at one end, the time at the other and
//: nothing between: the widest empty strip of it measured 60% of the hero at
//: 1024, 72% at 1440 and 78% at 1920 (`scratchpad/ui-sweeps/hero675.js`). A
//: hero earns that width by answering the question somebody opens a notebook
//: with, which is "what needs me today", so the other half of it is four
//: tiles: what is due today, today's meetings, the filings waiting and the
//: note you were last in.
//:
//: Always four, in one order, each with a calm state: tiles that come and go
//: with the day's data would move under the pointer and leave the empty
//: middle back on a quiet day. Every number is a read the dashboard already
//: makes (`dashReminders`, `fetchDashStats`, `dashEntries`, all shared with
//: the widgets), so the glance costs no request and no model.
//:
//: Pure, so the arithmetic runs in node (tests/test_inbox_675_hero.py); `go`
//: is a token `renderDashGlance` turns into the press, not a closure.
function dashGlanceFacts({ reminders = [], stats = null, entries = [], now = new Date() } = {}) {
  const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const time = (d) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", ...clockOptions() });
  const byDue = (a, b) => new Date(a.due_at) - new Date(b.due_at);
  const open = (reminders || []).filter((r) => r && !r.done).sort(byDue);
  const today = open.filter((r) => new Date(r.due_at) < endOfDay);
  //: **The one count of due reminders** (ai/due_summary.py is its twin): due today
  //: when the day is today (a time earlier today is still today), overdue when it
  //: is before today, later otherwise. The sub line and this tile both read it.
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const counted = { today: 0, overdue: 0, later: 0 };
  for (const r of open) {
    const at = new Date(r.due_at);
    if (at < startOfDay) counted.overdue += 1;
    else if (at < endOfDay) counted.today += 1;
    else counted.later += 1;
  }
  const word = (n) => ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"][n] || String(n);
  const say = [[counted.today, "due today"], [counted.overdue, "overdue"]].filter(([n]) => n).map(([n, what]) => `${word(n)} ${what}`).join(", ");
  const overdue = counted.overdue;
  const next = open.find((r) => new Date(r.due_at) >= endOfDay);
  let dueHint = "No reminders set";
  if (today.length) {
    const first = today[0];
    const when = new Date(first.due_at);
    dueHint = when < startOfDay ? `${first.text}, overdue` : `${first.text} at ${time(when)}`;
  } else if (next) {
    dueHint = `Next: ${next.text}, ${new Date(next.due_at).toLocaleDateString([], { weekday: "long" })}`;
  }
  const due = {
    id: "due",
    icon: "ph:alarm",
    count: today.length,
    overdue,
    label: today.length ? say.charAt(0).toUpperCase() + say.slice(1) : "Nothing due today",
    ...counted,
    say: say.charAt(0).toUpperCase() + say.slice(1),
    hint: dueHint,
    go: "reminders",
  };

  //: A meeting is a note typed Meeting with a `date:` in its property block,
  //: the writer's wall clock (entry/meetings.py); today's are the ones whose
  //: date is today's, the next one the first still to start.
  const meetingsToday = [];
  for (const entry of entries || []) {
    const when = dashMeetingWhen(entry, now);
    if (when) meetingsToday.push({ entry, when });
  }
  meetingsToday.sort((a, b) => a.when - b.when);
  const upcoming = meetingsToday.find((m) => m.when >= now) || meetingsToday[meetingsToday.length - 1];
  const name = (entry) => (entry.title || "").trim() || "A meeting";
  const n = meetingsToday.length;
  const meetings = {
    id: "meetings",
    icon: "ph:users-three",
    count: n,
    label: n ? `${nounCount(n, "meeting")} today` : "No meetings today",
    hint: !n
      ? "Nothing on the calendar"
      : upcoming.when >= now
        ? `${name(upcoming.entry)} at ${time(upcoming.when)}`
        : `${name(upcoming.entry)} was at ${time(upcoming.when)}`,
    go: n ? { entry: upcoming.entry.id } : "meetings",
  };

  //: Null when the stats read failed: "Nothing to file" would be a claim.
  const waiting = stats && Number.isFinite(stats.to_review) ? stats.to_review : null;
  const review = {
    id: "review",
    icon: "ph:checks",
    count: waiting,
    label: waiting === null ? "Filings to check" : waiting ? `${waiting} to file` : "Nothing to file",
    hint: waiting ? "Atlas was unsure where these go" : waiting === 0 ? "Every note has a home" : "Open the list",
    go: "review",
  };

  const last = dashContinueNote(entries);
  const lastTitle = last
    ? (last.title || "").trim() || noteNamePlain(last.content) || "Your last note"
    : "";
  const resume = {
    id: "continue",
    icon: last ? "ph:arrow-u-up-left" : "ph:pencil-simple",
    count: null,
    label: last ? lastTitle : "No notes yet",
    hint: last ? "Pick up where you left off" : "Your first note starts here",
    go: last ? { entry: last.id } : "capture",
  };
  return [due, meetings, review, resume];
}

//: When a note is a meeting today: its `date:` as a local Date, or null. A
//: date with no time is the start of the day, so it sorts first.
function dashMeetingWhen(entry, now) {
  const content = (entry && entry.content) || "";
  if (!content.startsWith("---")) return null;
  const end = content.indexOf("\n---", 3);
  if (end < 0) return null;
  const block = content.slice(3, end);
  if (!/^type:\s*meeting\s*$/im.test(block)) return null;
  const found = /^date:\s*(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/m.exec(block);
  if (!found) return null;
  const [, y, mo, d, h = "0", mi = "0"] = found;
  if (Number(y) !== now.getFullYear() || Number(mo) !== now.getMonth() + 1 || Number(d) !== now.getDate()) return null;
  return new Date(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi));
}

//: Drawn at every view and shown at Focused only (the CSS): the reads are the
//: widgets' own, so drawing it costs nothing, and a switch of view needs no
//: render. Tiles are the tile recipe (`quickLinkButton`), toned for a card.
async function renderDashGlance() {
  const host = $("dash-glance");
  if (!host) return;
  //: The newest draw wins; its number is held on the host, not in a
  //: top-level `let` (the global-scope ratchet).
  const serial = String((Number(host.dataset.glanceDraw) || 0) + 1);
  host.dataset.glanceDraw = serial;
  //: Four placeholders first, so the hero holds its height while the reads
  //: land (INBOX 577's rule for this banner: no shift at boot).
  if (!host.childElementCount) {
    for (let i = 0; i < 4; i++) {
      const hold = document.createElement("span");
      hold.className = "quick-link dash-glance-hold";
      hold.setAttribute("aria-hidden", "true");
      host.append(hold);
    }
  }
  const [reminders, stats, entries] = await Promise.all([
    dashReminders().catch(() => []),
    fetchDashStats().catch(() => null),
    dashEntries().catch(() => []),
  ]);
  if (serial !== host.dataset.glanceDraw || !host.isConnected) return;
  const facts = dashGlanceFacts({ reminders, stats, entries });
  const press = {
    reminders: () => switchTab("reminders"),
    meetings: () => showNotesFilter("tag:meeting"),
    review: () => showNotesFilter("is:review"),
    capture: () => startNewNote(),
  };
  host.replaceChildren(
    ...facts.map((fact) => {
      const run = typeof fact.go === "object" ? () => flashEntry(fact.go.entry) : press[fact.go];
      const tile = quickLinkButton({ icon: fact.icon, label: fact.label, hint: fact.hint, run });
      tile.classList.remove("quick-action");
      tile.dataset.glance = fact.id;
      tile.title = `${fact.label}. ${fact.hint}`;
      //: A trailing caret: the tile is a way somewhere, and in a wide tile
      //: it gives the far end something to say rather than an empty box.
      const go = document.createElement("i");
      go.className = "ph ph-caret-right dash-glance-go";
      go.setAttribute("aria-hidden", "true");
      tile.append(go);
      //: A tile with nothing in it is quieter than one with something, so
      //: the eye lands on what needs doing (and on overdue first).
      if (fact.count === 0) tile.classList.add("is-calm");
      if (fact.overdue) tile.classList.add("is-overdue");
      return tile;
    })
  );
}

{
  //: The hero's one action at Focused, where Quick access (whose first tile
  //: is the same New note) is folded away.
  const add = $("dash-hero-new");
  if (add) add.addEventListener("click", () => startNewNote());
}

// The greeting can address you by name, but the setting for it is one field
// among a dozen in Preferences, so for most people it is simply never found,
// and the greeting looks like it just doesn't do that (user-reported). One
// quiet offer beside the greeting, only while no name is set, and it stops
// asking the moment you either set one or dismiss it.
function renderNameNudge(greetingEl) {
  const existing = document.getElementById("dash-name-nudge");
  if (existing) existing.remove();
  const name = ((prefsCache && prefsCache.display_name) || "").trim();
  //: Not while the Get started card is, or is about to be, up: it carries the same
  //: offer and removes this one when it lands, which moved the page 32px.
  if (name || prefs.get("nameNudgeDismissed", null) === "1") return;
  if (!prefs.get("getStartedHidden", null) && !prefs.get("firstStepsHidden", null)) return;

  const wrap = document.createElement("span");
  wrap.id = "dash-name-nudge";
  wrap.className = "name-nudge";
  const add = document.createElement("button");
  add.type = "button";
  add.className = "ghost small";
  setLabel(add, "ph:hand-waving Add your name");
  add.title = "Let the greeting call you by name";
  add.addEventListener("click", async () => {
    await openSettingsModal("preferences");
    const field = $("pref-display-name");
    field.focus();
    field.select();
  });
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "ghost small icon-only";
  setLabel(dismiss, "ph:x");
  dismiss.title = "Don't ask again";
  dismiss.setAttribute("aria-label", "Dismiss the name suggestion");
  dismiss.addEventListener("click", () => {
    prefs.set("nameNudgeDismissed", "1");
    wrap.remove();
  });
  wrap.append(add, dismiss);
  greetingEl.after(wrap);
}
// --- masonry packing for the dashboard ---------------------------------------
// CSS grid can't size rows to content per-column, so each card is given a row
// span matching its measured height. Short widgets then stack vertically
// inside a row instead of being stretched to match the tallest one.

let dashResizeObserver = null;

//: **Three passes, not one per card** (INBOX 400). Written per card, the
//: loop set a card's span, read its height and set it again, so every card
//: after the first read a layout the previous card had just dirtied: one
//: forced layout of the whole page per widget. Profiled on a switch to the
//: dashboard (`f2-prof.js`), that was 14.7ms of a 22ms switch. Every card's
//: height depends on its own content and the column width alone, never on
//: another card's span, so all of them can be released first, measured
//: together against one layout, and set together.
//: **A 1px row unit and no row gap** (unslop 1103, 3). The unit was 8px with a
//: 16px row gap, so a span could only grow in 24px steps and stacked cards sat
//: 18 to 36px apart where side-by-side ones sit 16 (33, 18.2, 28.1, 33.2 ...
//: measured). The gap between stacked cards is now the card gap, added to the
//: height before it is rounded up to a whole pixel: 16 to 17px, always.
function sizeDashWidgetSpan(height, rowUnit, rowGap, cardGap) {
  return `span ${Math.max(1, Math.ceil((height + cardGap + rowGap) / (rowUnit + rowGap)))}`;
}

function sizeDashWidgets() {
  const grid = $("dash-grid");
  //: **Never while the tab is hidden** (dashcls-1031): the observer also fires
  //: as the grid goes `display: none`, every card measured 0px and was given
  //: `span 1`, and the next visit painted them stacked until it re-measured
  //: (layout shift 0.34). The grid's own fire on showing it measures it right.
  //: The class is the test, and the cards' own boxes are the rest: the visibility API needs a clean
  //: style tree, so it paid the whole-page style recalc as a flush of its own (129 ms at 4x on a
  //: switch to Notes, W25 D7; 34 to 46ms of boot, INBOX 1741). A grid that is not drawn measures
  //: every card 0px, and that is the bail below, before any write.
  if (!grid || grid.closest(".hidden")) return;
  const cards = [...grid.querySelectorAll(".dash-widget")];
  //: **One layout a call, not three** (INBOX 1591: the dashboard's first reads were 85ms of
  //: forced layout inside the notes response). The grid is `align-items: start`, so a card is
  //: its content's height whatever span it holds (identical at 1440, 1000, 700 and 390): the
  //: release to `span 1` before the read only dirtied the layout the read then paid for. And
  //: reads go before any write.
  const heights = cards.map((card) => card.getBoundingClientRect().height);
  if (!heights.some(Boolean)) return;
  const styles = getComputedStyle(grid);
  const rowUnit = Number.parseFloat(styles.getPropertyValue("grid-auto-rows")) || 1;
  const rowGap = Number.parseFloat(styles.rowGap) || 0;
  const cardGap = Number.parseFloat(styles.columnGap) || 16;
  cards.forEach((card, i) => {
    card.style.gridRowEnd = sizeDashWidgetSpan(heights[i], rowUnit, rowGap, cardGap);
  });
  grid.classList.add("spans-ready");
}

// Widget bodies fill in asynchronously, so re-measure whenever one changes
// size rather than only once at render time.
function watchDashWidgets() {
  const grid = $("dash-grid");
  if (!grid || typeof ResizeObserver === "undefined") {
    sizeDashWidgets();
    return;
  }
  dashResizeObserver?.disconnect();
  let queued = false;
  dashResizeObserver = new ResizeObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      //: Not behind the veil (INBOX 1741): the grid is hidden while its cards fill and `renderDashboard`'s settle
      //: sizes it once as it lifts; a pass per fill was 5 or 6 forced layouts at boot.
      if (!grid.classList.contains("dash-filling")) sizeDashWidgets();
    });
  });
  //: Observing fires once for every card, so the first sizing is the observer's, a frame on,
  //: with the widgets drawn rather than empty: sizing here as well was a whole-page layout
  //: (46 + 25ms at 4x) inside the response that delivered the notes.
  for (const card of grid.querySelectorAll(".dash-widget")) {
    dashResizeObserver.observe(card);
  }
}

// --- the dashboard's menu: everything one press away (INBOX 436) -------------
//
// Six bands stood between the hero and the first widget at 1440, 462px of
// them (`scratchpad/ui-sweeps/dash436.js`): the search, Start something, Jump
// to, Run a skill, four stat tiles and a sparkline, and a "Your dashboard"
// bar. Two stay: the search, now with the page's one menu beside it, and the
// Start something tiles, which the owner asked to keep as they are. Jump to,
// Run a skill and the layout bar are that menu's groups (`dashMoreItems`); the
// stat tiles' figures are the hero's line, the status bar and three widgets.
//
// Anything targeting the Notes tab must name its sub-tab: the tab remembers
// the last of capture, ask and browse, so "switchTab('notes') then focus"
// only works if it was left on the right one (an audit found New note failing
// from two of the three).
//
//: **"Ask" goes where a question can be answered today** (INBOX 266 part 1).
//: Both of the dashboard's asking doors went to the Chat tab, and with no
//: model running the Chat composer is disabled (`data-needs-model`): driven
//: from a fresh load (`scratchpad/ui-sweeps/clicks.js`), "Ask AI" landed on a
//: greyed box with the caret nowhere, and the empty notebook's "Ask your
//: notebook" card promised "Works on keywords even with no AI running" and
//: then opened the one place that does not. Notes, Ask is the place that
//: does: it searches without a model and says so. So the door picks: Chat
//: when a model is up, Notes, Ask when it is not, and the caret goes into
//: whichever box is shown after the tab has finished arriving (`switchTab`
//: awaits the tab's module before its own focus handling, so a same-turn
//: `focus()` could land on a page that is not drawn yet).
async function openAskFromDashboard() {
  const offline = aiIsOff();
  await switchTab(offline ? "notes" : "chat");
  if (offline) {
    showNotesSection("ask");
    $("question")?.focus();
  } else {
    $("chat-input")?.focus();
  }
}

//: **Quick access's default five** (they were the "Start something" tiles):
//: what you can begin from here, each a verb with a line saying what happens.
//: The first of them carries the highlight (`quickTintKey`). The `id`s are what the stored list
//: (`dashboard_quick_access`) holds; the person's own choices are added from
//: the command palette's catalogue (`quickCatalogue`), never typed in here.
const QUICK_ACCESS_MAX = 8;
const QUICK_START = [
  {
    id: "new-note",
    icon: "ph:pencil-simple",
    label: "New note",
    hint: "Atlas files it for you",
    run: () => startNewNote(),
  },
  {
    id: "ask-ai",
    icon: "ph:chat-circle",
    label: "Ask your notes",
    hint: "Answered from your notes",
    run: () => openAskFromDashboard(),
  },
  { id: "sketch", icon: "ph:palette", label: "Sketch", hint: "Draw, then keep it as a note", run: () => openSketch() },
  {
    id: "remind-me",
    icon: "ph:alarm",
    label: "Remind me",
    hint: "Say when, in plain words",
    run: () => {
      switchTab("reminders");
      $("reminder-magic").focus();
    },
  },
  //: **A meeting, not a recorder** (INBOX 644: "tucked away"). This tile
  //: opened the recorder, a dialog whose one control is Record, so the
  //: everyday case, notes typed in a meeting, was five clicks through a
  //: template. It starts a meeting note now; recording is inside it. The id
  //: stays, so a saved Quick access keeps its tile.
  {
    id: "meeting-notes",
    icon: "ph:users-three",
    label: "New meeting",
    hint: "Agenda, notes, action items",
    run: () => openNewMeeting(),
  },
];

//: What the tab bar cannot do: open the features browser and the command
//: palette (findable only by already knowing Ctrl+K; a row is how you learn
//: a shortcut). Every tab is one click away in the tab bar.
const QUICK_GO = [
  { icon: "ph:toolbox", label: "Tools & features", hint: "Everything the app can do, searchable", run: () => openFeatures() },
  { icon: "ph:command", label: "Commands", hint: "The command palette (Ctrl+K)", run: () => openPalette() },
];

//: How many recently-run skills get a row in the menu. Two: a skill you ran
//: once last month is not quick access to anything.
const QUICK_SKILL_SLOTS = 2;

//: Skills that have actually been run, most recent first. Written by
//: `startSkill`, so it covers both the dropdown and a run the agent started
//: itself (§33): if the model keeps reaching for a skill, that is evidence it
//: belongs on the dashboard too.
const RECENT_SKILLS_KEY = "recentSkills";

//: When each of them was last run, name to ISO timestamp. A second key rather
//: than a richer `recentSkills`, and that is deliberate: the list is written
//: by three call sites and read by two, and a profile that has run a skill
//: already has an array of plain strings on disk. Changing that shape in
//: place means a migration, and the last time this list changed shape without
//: one it left a `null` in every affected profile that broke the whole
//: dashboard on load (see `noteSkillRun`). A separate map has no old shape to
//: be wrong about: a name that is missing from it simply has no time to show.
const SKILL_RUN_TIMES_KEY = "recentSkillTimes";

function skillRunTimes() {
  try {
    const stored = prefs.json(SKILL_RUN_TIMES_KEY, {});
    return stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
  } catch {
    return {};
  }
}

function noteSkillRun(name) {
  // **Refuse a nameless run rather than storing it.** This guard exists
  // because the absence of it cost the whole dashboard, and the failure is
  // worth recording in full because nothing about it is visible at this line.
  //
  // §88.0 fixed a call site that read `startSkill(skill.name)` where an object
  // was expected. While that bug was live, `skill` was a *string*, so
  // `skill.name` was `undefined`, and this function was called with it. That
  // alone would have been harmless, but `JSON.stringify` converts `undefined`
  // inside an array to **`null`**, so what landed in localStorage was a real
  // `null` element, not a missing one. Fixing the call site stopped new poison
  // and did nothing about the `null` already written, which persists across
  // every reload, forever, in any profile that ran a skill during that window.
  //
  // The damage then surfaced nowhere near here: `recentSkillLinks` below
  // reads that array on every dashboard render, and `withoutLeadingEmoji`
  // calls `.replace()` on the `null`. That throw propagated out of
  // the quick links -> `renderDashboard` -> `refreshActiveTab`, i.e. it
  // escaped *before* `grid.replaceChildren()` and the widget loop had run, so
  // the reported symptoms were "the dashboard widgets are completely broken"
  // and a toast reading "Couldn't load this tab: Cannot read properties of
  // null (reading 'replace')", two reports, one cause, neither of them
  // pointing at the skills feature that actually caused it.
  //
  // The shape CLAUDE.md names: a value that is invalid where it is *used*,
  // not where it is *set*, does its damage nowhere near the code at fault.
  if (typeof name !== "string" || !name) return;
  let recent = [];
  try {
    recent = prefs.json(RECENT_SKILLS_KEY, []);
  } catch {
    recent = [];
  }
  recent = [name, ...recent.filter((n) => n !== name)].slice(0, 8);
  prefs.set(RECENT_SKILLS_KEY, JSON.stringify(recent));
  // The time goes in beside it, pruned to the names still on the list so the
  // map cannot grow forever in a profile that tries a lot of skills.
  const times = skillRunTimes();
  times[name] = new Date().toISOString();
  for (const key of Object.keys(times)) {
    if (!recent.includes(key)) delete times[key];
  }
  prefs.set(SKILL_RUN_TIMES_KEY, JSON.stringify(times));
}

//: A skill's name usually starts with its own emoji, "stethoscope Notebook health
//: check", "tag Clean up my tags", and the quick-link then put Skill in front of
//: it, so those two chips wore two icons each while every other chip in the
//: row wore one. Reported as clutter, and it was: measured at 224px and 216px
//: against 107–169px for the fixed chips, i.e. the two least important buttons
//: in the row were the two widest.
//:
//: The Skill is the one that stays, because it carries what the row does not
//: otherwise say: this chip *runs* something rather than opening a page. The
//: skill's own emoji is still on it everywhere skills are listed.
const LEADING_EMOJI = /^(\p{Extended_Pictographic}(?:️|‍\p{Extended_Pictographic})*)\s*/u;

function withoutLeadingEmoji(name) {
  // `String(...)` rather than a bare `.replace`: this is the line that threw
  // for every profile carrying the poisoned `recentSkills` entry described in
  // `noteSkillRun`, and it took the whole dashboard down with it. The write
  // guard and the read filter below both prevent that now, so this coercion is
  // the third of three, but it is the cheapest, and it is the one standing
  // between any future bad value and another blank dashboard.
  const text = String(name ?? "");
  const stripped = text.replace(LEADING_EMOJI, "");
  // A skill named with nothing but an emoji would otherwise become a blank
  // chip; keeping the original is the lesser of the two.
  return stripped.trim() || text;
}

function recentSkillLinks() {
  let recent = [];
  try {
    recent = prefs.json(RECENT_SKILLS_KEY, []);
  } catch {
    return [];
  }
  if (!Array.isArray(recent)) return [];
  // **This filter is the repair, not just a guard.** The write side is fixed,
  // but a profile that ran a skill while the §88.0 bug was live already has a
  // `null` on disk and would keep crashing its own dashboard on every load
  // forever: a fix that only prevents new bad data would leave exactly the
  // people who hit the bug still broken. Rewriting the cleaned list back means
  // one load repairs the profile permanently.
  const clean = recent.filter((n) => typeof n === "string" && n);
  if (clean.length !== recent.length) {
    prefs.set(RECENT_SKILLS_KEY, JSON.stringify(clean));
  }
  const times = skillRunTimes();
  return clean.slice(0, QUICK_SKILL_SLOTS).map((name) => ({
    icon: "ph:lightning",
    label: withoutLeadingEmoji(name),
    // **What the row was missing**, INBOX 60: a skill pill said only its own
    // name, so the row could not answer "did I already run this today?",
    // which is the question you ask before spending a model call. The other
    // two groups carry a hint each and this one carried none.
    hint: times[name] ? `Last run ${relativeTime(times[name])}` : "Not run yet on this device",
    // The full name, unaltered, is what the button remembers itself by: the
    // use counter and `runSkill` both key off it, and stripping the emoji from
    // either would silently start a second tally or fail to find the skill.
    skillName: name,
    skill: true,
    run: () => {
      const known = allSkills().find((s) => s.name === name);
      // A skill can be deleted between runs. Sending the user to the picker is
      // more use than a button that fails.
      if (known) runSkill(known);
      else switchTab("chat");
    },
  }));
}

//: **How much of the dashboard is chrome, as the reader's choice.**
//:
//: INBOX 270, the owner: *"is there a way to declutter the dashboard a bit or
//: spread things out a bit?? idk it looks good but a lot is happening on it.
//: maybe something like the feed layout options with msn on microsoft bing??"*
//:
//: Measured from their screenshot at 1440 wide: five Start something tiles,
//: four Jump to pills, three skill chips, four stat tiles and a sparkline, and
//: then the "Your dashboard" heading. Six bands of chrome above the first
//: widget, which is the thing the page is named after.
//:
//: Three densities rather than a slider, the shape MSN's Feed layout uses and
//: the shape a person can hold in their head: Full is what shipped, Compact
//: folds the same things smaller, Focused shows the search and the widgets and
//: puts the rest one press away. **Nothing is deleted by any of them**: a
//: layout choice that removes a feature is a feature somebody cannot find
//: again, and this app has been told before what that costs.
//:
//: Per device, in `localStorage`, beside the layout itself rather than in
//: preferences: which density suits this screen is a fact about this screen.
const DASH_DENSITIES = ["full", "compact", "focused"];
const DASH_DENSITY_KEY = "dash-density";

function dashDensity() {
  const saved = prefs.get(DASH_DENSITY_KEY, null);
  return DASH_DENSITIES.includes(saved) ? saved : "full";
}

//: Whether the level was picked, as opposed to being the default.
function dashDensityChosen() {
  return DASH_DENSITIES.includes(prefs.get(DASH_DENSITY_KEY, null));
}

//: **The emblem is the hero's art, and art is what a density step spends**
//: (INBOX 279). The first cut of the three levels hid the mark outright at the
//: first step down and then kept a display-sized clock beside a greeting it had
//: cut to `--text-lg`, which is how the hero came to "lose a lot" at Compact
//: while Focused kept a bigger banner than Compact had.
//:
//: A size rather than a CSS rule because the mark is a p5 sketch drawn into a
//: canvas of that many pixels: scaling the holder would either leave a 46px box
//: around a 30px drawing or resample the canvas. 0 means the level does not
//: carry it at all, and the CSS hides the holder to match.
const DASH_EMBLEM_SIZE = { full: 46, compact: 30, focused: 0 };

//: **The dashboard has drawn its banner at least once.** Set by the render,
//: read by the density switch, because the switch used to ask whether a canvas
//: was already in the holder instead, and that question answers "no" for the
//: one case it exists to serve: Focused empties the holder, so switching back
//: to Full or Compact found no canvas, skipped the repaint, and the mark was
//: gone for good (the owner, 2026-09-21: "the animated logo is gone from the
//: dashboard, it should be in both the full and compact dashboard view and
//: shouldnt dissappear permanently").
let dashEmblemDrawn = false;

//: The dashboard's mark, when Appearance swaps the logo for a face: yours,
//: or the persona the greeting speaks as (the chat's own when it matches
//: Chat). Null keeps the logo. Here, not in avatars.js: the dashboard asks at
//: boot, before that file is in.
function dashboardMarkSeed() {
  const choice = appearancePref("dash-mark", "logo");
  if (choice === "me") return userMarkSeed();
  //: Atlas by name, whoever the greeting speaks as (the owner: "the
  //: dashboard mark should have atlas as an option as well"). "Greeting
  //: persona" only shows Atlas while Atlas is that persona.
  if (choice === "atlas") return "Atlas";
  if (choice === "persona") {
    return prefsCache?.dashboard_persona || document.getElementById("persona-select")?.value || personaDisplayName(prefsCache?.active_persona) || "Atlas";
  }
  return null;
}

function paintDashFace(holder, face, size) {
  //: The logo's sketch stops first: a p5 loop on a canvas that is no
  //: longer in the page still draws every frame.
  const sketch = typeof emblemInstances !== "undefined" ? emblemInstances.get(holder) : null;
  if (sketch) {
    sketch.remove();
    emblemInstances.delete(holder);
    emblemObservers?.get(holder)?.disconnect();
    emblemObservers?.delete(holder);
  }
  holder.replaceChildren(nameMarkLive(face, size));
}

function paintDashEmblem() {
  const holder = $("dash-hero-emblem");
  if (!holder) return;
  dashEmblemDrawn = true;
  const size = DASH_EMBLEM_SIZE[dashDensity()] ?? DASH_EMBLEM_SIZE.full;
  //: A sketch drawn into a hidden holder measures zero (the holder is
  //: `display: none` at Focused), so the level that does not carry the mark
  //: does not draw one either; switching back re-enters through
  //: `applyDashDensity` below.
  if (!size) {
    holder.replaceChildren();
    return;
  }
  //: A face instead of the logo when Appearance asks (avatars.js, which may
  //: not be in yet: the face is drawn when it is).
  const face = dashboardMarkSeed();
  if (face) {
    afterCharacters(() => paintDashFace(holder, face, size));
    return;
  }
  holder.querySelector(".nm-live")?.remove();
  renderEmblem(holder, size, { animate: true });
}

//: **The mark chooses itself where it is** (the owner: "I want to be able to
//: right click the dashboard widget and be able to change it between atlas,
//: my own avatar, the dashbaord persona avatar, or the animated app logo").
//: The same four choices as Appearance, Dashboard mark, and the same write:
//: the stored choice, the select kept in step, the mark redrawn. The menu is
//: the recipe's (`openMenuAtPoint`, markdown.js), with a hold as its twin on
//: touch (`wireLongPress`), like every right-click menu in the app.
const DASH_MARK_CHOICES = [
  ["logo", "The app's logo"],
  ["atlas", "Atlas"],
  ["me", "Your face"],
  ["persona", "The greeting's persona"],
];

function dashMarkMenu(x, y) {
  const now = appearancePref("dash-mark", "logo");
  const items = DASH_MARK_CHOICES.map(([value, label]) => ({
    label: `${now === value ? "ph:check" : "ph:dot-outline"} ${label}`,
    title: `Show ${label.toLowerCase()} here`,
    run: () => {
      try {
        prefs.set("dash-mark", value);
      } catch {
        // This session only.
      }
      const select = document.getElementById("dash-mark");
      if (select) select.value = value;
      paintDashEmblem();
    },
  }));
  openMenuAtPoint(items, "Dashboard mark", x, y);
}

{
  const holder = document.getElementById("dash-hero-emblem");
  if (holder) {
    //: A gesture with no visible control names itself (Settings, Appearance has the same choice).
    holder.title = "Right-click or hold to change this mark";
    holder.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      dashMarkMenu(event.clientX, event.clientY);
    });
    wireLongPress(holder, (event, point) => dashMarkMenu(point.x, point.y));
  }
}

function applyDashDensity(value, { persist = true } = {}) {
  const density = DASH_DENSITIES.includes(value) ? value : "full";
  //: Stored only when chosen: the wiring's own first call used to write
  //: "full" for every install, which made the default look like a choice.
  if (persist) prefs.set(DASH_DENSITY_KEY, density);
  const page = document.getElementById("tab-dashboard");
  //: A data attribute on the page, and every rule keyed off it in CSS. The
  //: alternative, adding and removing classes on six elements from here, is
  //: how one of them ends up in the wrong state after a render that rebuilt
  //: it: the attribute survives, a class on a replaced node does not.
  //:
  //: **Full at the app's Compact density is the compact dashboard**
  //: (WORLD_CLASS_PLAN 22.1 item 2). The app's density is the instruction
  //: "less air everywhere", and on a window 700px tall or less it is Compact
  //: by default (`effectiveDensity`, settings.js): measured at 1093x614 the
  //: first widget started 32px under the fold with the hero, the Start
  //: something tiles and the stats at full size. Focused stays Focused.
  //: **Unless Full was picked and Compact is only the window's height**
  //: (INBOX 904 B12 and B64: "why does the quick access look so small on the
  //: full view", "sometimes loses its full form"). The View menu ticked Full
  //: while a window under 700px made the tiles 34px tall with no hint line.
  //: A choice always wins over Auto: an app density chosen in Appearance still
  //: folds Full, a short window alone no longer does once Full is chosen.
  const appCompact = document.documentElement.dataset.density === "compact";
  const appChosen = Boolean(prefs.get("density", null));
  if (page) page.dataset.density = density === "full" && appCompact && (appChosen || !dashDensityChosen()) ? "compact" : density;
  //: The mark is the one part of the banner CSS cannot resize (see
  //: `DASH_EMBLEM_SIZE`), so the level change redraws it, but only once the
  //: dashboard has drawn one: this function also runs at wiring time, before
  //: the first render, and drawing there would race the render's own call.
  if (page && dashEmblemDrawn) paintDashEmblem();
}

//: Once: the level is applied to the page before the first render reads it.
//: The choice itself is a row of the menu (`dashMoreItems`), which applies it
//: and rebuilds the menu so its tick moves.
function wireDashDensity() {
  if (wireDashDensity.done) return;
  wireDashDensity.done = true;
  applyDashDensity(dashDensity(), { persist: false });
}

//: **A tile's highlight** (INBOX 589, the owner: "only the new note link
//: widget is a different colour. should the one in the first position be
//: highlighted by default with the option to highlight the others other
//: colours too??"). The key a tile is painted with: a choice the person made
//: (`dashboard_quick_tints`, tile id to "accent", "none" or a
//: `CATEGORY_PALETTE` key; set from the tile's menu while arranging) wins;
//: without one, the first tile is the accent and the rest are plain. By
//: position, not by name: whatever is put first is where the eye starts, so
//: New note moved to third is no longer the row's suggestion. "" is plain.
function quickTintKey(id, index, tints) {
  const chosen = tints && typeof tints === "object" ? tints[id] : undefined;
  if (chosen === "none") return "";
  if (chosen === "accent" || Object.hasOwn(CATEGORY_PALETTE, chosen ?? "")) return chosen;
  return index === 0 ? "accent" : "";
}

//: A tint key as the colour CSS mixes from, and the colour its icon takes:
//: the accent's icon is `--accent-text` (the accent itself is a fill colour
//: and can sit under 3:1 on the card), a palette hue is its own icon, since
//: each of the twelve clears 3:1 as a mark on both themes' grounds.
function quickTintColours(key) {
  if (key === "accent") return ["var(--accent)", "var(--accent-text)"];
  const hex = CATEGORY_PALETTE[key];
  return [hex, hex];
}

function quickLinkButton(link, tint = "") {
  const button = document.createElement("button");
  button.className = "quick-link quick-action";
  if (tint) {
    const [fill, ink] = quickTintColours(tint);
    button.classList.add("quick-link-tinted");
    button.dataset.tint = tint;
    button.style.setProperty("--quick-tint", fill);
    button.style.setProperty("--quick-tint-ink", ink);
  }
  button.type = "button";
  // The label truncates in a narrow tile, so hovering finishes the sentence.
  button.title = link.hint || link.label;
  const icon = document.createElement("span");
  icon.className = "quick-link-icon";
  setLabel(icon, link.icon);
  icon.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.className = "quick-link-text";
  const label = document.createElement("span");
  label.className = "quick-link-label";
  setLabel(label, link.label);
  const hint = document.createElement("span");
  hint.className = "quick-link-hint";
  setLabel(hint, link.hint);
  text.append(label, hint);
  button.append(icon, text);
  //: A tile whose code is fetched on the first press (the Diagram builder: the Library bundle and its own files, seconds on
  //: a slow machine) shows the working ring and takes no second press until it has opened (the owner, 2026-11-09).
  button.addEventListener("click", () => {
    const pending = link.run();
    if (typeof pending?.then !== "function") return;
    const ring = setTimeout(() => setBusy(button, true), 150);
    pending.then(null, () => {}).then(() => (clearTimeout(ring), setBusy(button, false)));
  });
  return button;
}

async function saveQuickAccess(ids) {
  prefsCache = await apiJson("/preferences", { method: "PUT", body: JSON.stringify({ dashboard_quick_access: ids }) }).catch(() => prefsCache);
}

function quickTints() {
  const tints = prefsCache?.dashboard_quick_tints;
  return tints && typeof tints === "object" ? tints : {};
}

async function saveQuickTints(tints) {
  prefsCache = await apiJson("/preferences", { method: "PUT", body: JSON.stringify({ dashboard_quick_tints: tints }) }).catch(() => prefsCache);
}

//: True while the row is being arranged: the editing view and its picker are
//: quick-access.js (lazy: only a person who customises pays for it).
let quickEditing = false;

//: **The note you were last in**, the menu's Continue row (INBOX 60). Most
//: recently *touched*, where touching is opening or editing, and not created.
//: Reported: "the opens a note you opened or edited most recently button
//: doesnt update and just shows my latest note". It ranked on `updated_at`
//: alone, which only moves when the text changes, so reading an old note left
//: it pointing at whatever was newest. `last_opened_at` is stamped by
//: `GET /entries/{id}` beside the access count (routes_entries), and the row
//: takes whichever of the three is latest: null for every note nobody has
//: opened since the column existed, which is why this is a max and not a
//: preference.
function dashContinueNote(entries) {
  if (!Array.isArray(entries)) return null;
  const touched = (entry) => {
    const times = [entry.last_opened_at, entry.updated_at, entry.created_at]
      .map((value) => (value ? new Date(value).getTime() : 0))
      .filter((value) => Number.isFinite(value));
    return Math.max(0, ...times);
  };
  return [...entries].filter((entry) => entry && !entry.is_draft).sort((a, b) => touched(b) - touched(a))[0] || null;
}

const DASH_VIEW_LABELS = { full: "Full", compact: "Compact", focused: "Focused" };

//: **What the first screen used to spell out in bands, one press away.** Three
//: groups, drawn as hairlines (`kebabMenu`'s `group`): go back to the last
//: note, run a skill, find a feature. Fixed order, no use counter: a menu
//: whose rows move is a menu you re-read. Arranging the page is Customise.
function dashMoreItems(entries) {
  const row = (link, group) => ({ label: `${link.icon} ${link.label}`, title: link.hint || link.label, group, run: link.run });
  const items = [];
  const last = dashContinueNote(entries);
  if (last) {
    // Cut at a word with an ellipsis: a bare slice ended on "responds to the
    // blu", which reads as a typo rather than as more text.
    const preview = clipText(notePreviewText(last.content || ""), 36) || "your last note";
    items.push({
      label: `ph:arrow-u-up-left Continue: ${preview}`,
      title: "Opens the note you opened or edited most recently",
      group: "resume",
      run: () => flashEntry(last.id),
    });
  }
  for (const link of recentSkillLinks()) {
    // The full name is in the title; the row says when it last ran, which is
    // the question asked before spending a model call (INBOX 60).
    items.push({ ...row(link, "skills"), title: `Run the skill \u201c${link.skillName}\u201d: it answers in the chat. ${link.hint}` });
  }
  items.push({ label: "ph:lightning All skills\u2026", title: "Every skill, in the chat's skill picker", group: "skills", run: () => switchTab("chat") });
  for (const link of QUICK_GO) items.push(row(link, "find"));
  return items;
}

//: **Arranging the page is its own control, beside the ⋯** (INBOX 488, the
//: owner: "confusing to have the widget management stuff in the meatball menu
//: button above the meatball menu button which covers the quick access"). The
//: ⋯ is for doing (Continue, skills, Tools & features, Commands); Customise is
//: for arranging this page (view, widgets, layout and the Quick access row,
//: whose own ⋯ it replaces), so one menu no longer opens over the other.
//: Below 600 the view is not offered: a phone's Full is already compact.
function dashCustomiseItems() {
  const items = [];
  if (!window.matchMedia("(max-width: 599.98px)").matches) {
    //: What the page is showing, not what is stored: with no choice made, a
    //: short window shows Compact, and the tick used to say Full.
    const current = document.getElementById("tab-dashboard")?.dataset.density || dashDensity();
    items.push({
      label: "ph:layout View",
      group: "page",
      items: DASH_DENSITIES.map((value) => ({
        label: `${current === value ? "ph:check" : "ph:dot-outline"} ${DASH_VIEW_LABELS[value]}`,
        title: `Show the dashboard ${DASH_VIEW_LABELS[value].toLowerCase()}`,
        run: () => {
          applyDashDensity(value);
          renderDashMore();
        },
      })),
    });
  }
  items.push({ label: "ph:squares-four Widgets\u2026", title: "Add, remove or widen any widget", group: "page", run: () => $("dash-widgets-open").click() });
  items.push({
    label: dashEditMode ? "ph:check Done editing" : "ph:arrows-out-cardinal Edit layout",
    title: "Move, widen and remove the widgets on this page",
    group: "page",
    run: () => $("dash-edit").click(),
  });
  //: The way back from Get started's Hide or Mark all as done (INBOX 1301 D3).
  if (prefs.get("getStartedHidden", null) === "1" || prefs.get("getStartedDone", null) === "1") {
    items.push({
      label: "ph:list-checks Show first steps",
      title: "The first steps card and button, as they were",
      group: "page",
      run: () => lazyScript("/js/first-run.js").then(() => getStartedShow()),
    });
  }
  items.push({ label: "ph:pencil-simple Edit quick access", title: "Add, remove and reorder the Quick access tiles", group: "quick", run: () => { quickEditing = true; renderQuickLinks(); } });
  //: The colours alone, keeping the tiles (INBOX 603, the owner: "reset the
  //: highlights on the quick access back to default or at least the first
  //: one being auto highlighted"). Only when one has been chosen.
  if (Object.keys(prefsCache?.dashboard_quick_tints || {}).length) {
    items.push({
      label: "ph:palette Reset highlights",
      title: "No colours chosen: the first tile is highlighted again",
      group: "quick",
      run: async () => { await saveQuickTints({}); renderQuickLinks(); renderDashMore(); },
    });
  }
  items.push({
    label: "ph:arrow-counter-clockwise Reset quick access",
    title: "Back to New note, Ask your notes, Sketch, Remind me and New meeting, the first highlighted",
    group: "quick",
    run: async () => { await saveQuickAccess([]); await saveQuickTints({}); renderQuickLinks(); },
  });
  return items;
}

//: Built at once from what is loaded, so the row never waits on a fetch and
//: the dock never shifts, then again when a cold start's notes arrive (the
//: Continue row is the only part that needs them).
let dashMoreSerial = 0;
async function renderDashMore() {
  const host = $("dash-more");
  if (!host) return;
  const serial = ++dashMoreSerial;
  const custom = $("dash-customise");
  if (custom) {
    const menu = kebabMenu(dashCustomiseItems(), "Customise the dashboard");
    const opener = menu.querySelector("button");
    //: The word in its own span so a phone can keep only the glyph.
    setLabel(opener, "ph:sliders-horizontal");
    const word = document.createElement("span");
    opener.querySelector("i")?.classList.add("ph-lead");
    word.className = "dock-word";
    word.textContent = "Customise";
    opener.append(word);
    opener.classList.remove("icon-only");
    opener.classList.add("ghost");
    custom.replaceChildren(menu);
  }
  const build = (entries) => host.replaceChildren(kebabMenu(dashMoreItems(entries), "More actions"));
  build(entriesEverLoaded ? allEntries : []);
  if (entriesEverLoaded) return;
  const entries = await dashEntries().catch(() => []);
  if (serial === dashMoreSerial && host.isConnected) build(entries);
}

//: The rows of "Tools and features" are `featureCatalog()` in app-features.js (lazy).

let featureAiTools = null; // fetched once per session

async function openFeatures() {
  overlayReturnFocus = document.activeElement;
  $("features-overlay").classList.remove("hidden");
  $("features-search").value = "";
  await lazyScript("/js/app-features.js");
  renderFeatures("");
  $("features-search").focus();
  if (featureAiTools === null) {
    featureAiTools = await apiJson("/chat/tools").catch(() => []);
    if (!$("features-overlay").classList.contains("hidden")) {
      renderFeatures($("features-search").value);
    }
  }
}

function closeFeatures() {
  $("features-overlay").classList.add("hidden");
  overlayReturnFocus?.focus?.();
  overlayReturnFocus = null;
}

//: **The first rows, then the rest as the list is scrolled to its end** (audit
//: 1031 Z11): drawing every row (212, 647 nodes) cost 76 ms of layout at 4x CPU
//: on each open and each keystroke; forty rows cost a fifth of that. The count
//: in the heading and the search still read the whole catalogue.
const FEATURES_FIRST_ROWS = 40;

function featureRow(item) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "feature-row";
  const name = document.createElement("span");
  name.className = "feature-name";
  setLabel(name, item.name);
  const desc = document.createElement("span");
  desc.className = "feature-desc muted";
  setLabel(desc, item.desc);
  row.append(name, desc);
  row.addEventListener("click", () => {
    closeFeatures();
    item.run();
  });
  return row;
}

function featuresPaint(list, steps) {
  list.moreObserver?.disconnect();
  let at = 0;
  const sentinel = document.createElement("div");
  sentinel.setAttribute("aria-hidden", "true");
  list.appendChild(sentinel);
  const observer = new IntersectionObserver((seen) => seen.some((e) => e.isIntersecting) && draw(FEATURES_FIRST_ROWS), { root: list, rootMargin: "400px 0px" });
  list.moreObserver = observer;
  const draw = (count) => {
    const part = document.createDocumentFragment();
    for (let rows = 0; at < steps.length && rows < count; at++) {
      const { heading, item } = steps[at];
      if (item) rows += 1;
      if (item) part.appendChild(featureRow(item));
      else {
        const h3 = document.createElement("h3");
        h3.className = "features-group";
        h3.textContent = heading;
        part.appendChild(h3);
      }
    }
    list.insertBefore(part, sentinel);
    if (at >= steps.length) {
      observer.disconnect();
      sentinel.remove();
    } else {
      //: Observed again, so a list still short of the sentinel asks for more.
      observer.unobserve(sentinel);
      observer.observe(sentinel);
    }
  };
  draw(FEATURES_FIRST_ROWS);
}

function renderFeatures(query) {
  const list = $("features-list");
  list.replaceChildren();
  const q = (query || "").trim().toLowerCase();
  const groups = featureCatalog();
  groups.push(featureCommandRows(groups));
  // The AI's own tools, straight from the backend registry.
  if (featureAiTools && featureAiTools.length) {
    groups.push({
      group: "What Atlas can do for you",
      items: featureAiTools.map((tool) => ({
        name: tool.name.replace(/_/g, " "),
        desc: tool.description + (tool.destructive ? " (asks you to confirm first)" : ""),
        //: The tool's own row in Settings, ringed, not the top of the pane.
        reveal: "ai-tool",
        arg: tool.name,
      })).map(catalogueRun),
    });
  }

  let shown = 0;
  const steps = [];
  for (const group of groups) {
    const matches = group.items.filter(
      (item) =>
        !q ||
        item.name.toLowerCase().includes(q) ||
        item.desc.toLowerCase().includes(q) ||
        (item.also || "").toLowerCase().includes(q) ||
        group.group.toLowerCase().includes(q)
    );
    if (!matches.length) continue;
    shown += matches.length;

    steps.push({ heading: group.group });
    for (const item of matches) steps.push({ item });
  }
  featuresPaint(list, steps);

  $("features-count").textContent = q
    ? `${shown} match${shown === 1 ? "" : "es"}`
    : `${shown} things Tessellate can do`;
  if (!shown) {
    const none = document.createElement("p");
    none.className = "muted";
    none.textContent = "Nothing matches that: try another word.";
    list.appendChild(none);
  }
}

//: **The first steps** (first-run.js, lazy; WORLD_CLASS_PLAN 25c): your
//: name, a first note and a first answer, ticked as each is done, and the
//: sample notebook. Above the grid rather than in it, so they stay past the
//: first note; a notebook that hid them, or finished them, never loads it.
function renderFirstStepsLazy() {
  const host = $("dash-first-steps");
  if (!host || !entriesEverLoaded) return;
  //: Hide Get started (INBOX 1301 D3) puts the menu away too: nothing to load.
  if (prefs.get("getStartedHidden", null) === "1") return void host.replaceChildren();
  const skip = dashEditMode || (allEntries.length && prefs.get("firstStepsHidden", null) === "1");
  //: The Get started menu beside Customise is drawn whether or not the card is.
  lazyScript("/js/first-run.js").then((ok) => ok && renderFirstSteps(host, skip));
}

//: A widget that throws, or never draws, says so and offers Retry (INBOX
//: 513): a render that never settled left its body loading for good. Promise.resolve() so a
//: synchronous renderer cannot break the dashboard loop.
const WIDGET_STALL_MS = 20000;

function mountWidgetBody(widget, body) {
  const failed = (message) => {
    if (!body.isConnected) return;
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = message;
    const retry = smallButton("ph:arrow-clockwise Retry", "Load this widget again", () => {
      body.replaceChildren();
      mountWidgetBody(widget, body);
    });
    body.replaceChildren(note, retry);
  };
  //: **Skeleton rows while it loads, never the word** (INBOX 596, the owner:
  //: "some skeleton loaders are missing like on the dashboard"). An empty
  //: body read "Loading…"; now it holds DESIGN.md's list skeleton
  //: (`showSkeletons`), which goes the moment the widget draws anything of
  //: its own, so a widget that fills in steps never shows both.
  showSkeletons(body, 2);
  const waiting = new MutationObserver(() => {
    if ([...body.children].some((el) => !el.classList.contains("skeleton"))) unskeleton();
  });
  const unskeleton = () => {
    waiting.disconnect();
    clearSkeletons(body);
  };
  waiting.observe(body, { childList: true });
  let settled = false;
  //: Cleared when the widget settles: a pending timer holds this closure, and
  //: through it the body, for the whole stall time (20 s) after the person has
  //: left (perf 1031 row 22: +630 detached nodes per Dashboard visit).
  let stall = 0;
  const done = () => {
    settled = true;
    clearTimeout(stall);
    unskeleton();
  };
  const drawn = Promise.resolve()
    .then(() => widget.render(body))
    .then(done)
    .catch(() => { done(); failed("Couldn't load this widget."); });
  stall = setTimeout(() => {
    if (!settled && !body.querySelector(":scope > :not(.skeleton)")) {
      unskeleton();
      failed("This is taking longer than it should.");
    }
  }, WIDGET_STALL_MS);
  return drawn;
}

//: **Back on the dashboard, the last picture stays** (INBOX 602, the owner:
//: "every time I go off the dashboard and go back on it, it is empty for a
//: second then loads"). A visit redrew the grid from nothing and hid it
//: until its widgets settled: 10 frames with no dashboard, 491 to 998ms
//: after the switch at 4x CPU (`scratchpad/ui-sweeps/loading598.js`). When
//: the layout is the one already drawn, each widget draws again into a body
//: laid out beside the old one at its width, unseen, and takes its place
//: when it is done; until then the old one is what shows.
function refreshDashWidgets(grid) {
  const drawing = [];
  for (const card of grid.querySelectorAll(".dash-widget:not(.dash-hidden)")) {
    const widget = DASH_WIDGETS[card.dataset.widget];
    const old = card.querySelector(":scope > .dash-body");
    if (!widget || !old) continue;
    const next = document.createElement("div");
    next.className = "dash-body";
    Object.assign(next.style, { position: "absolute", top: "0", insetInline: "var(--card-pad-x)", visibility: "hidden", pointerEvents: "none" });
    card.style.position = "relative";
    card.appendChild(next);
    drawing.push(
      mountWidgetBody(widget, next).then(() => {
        if (!next.isConnected) return;
        next.removeAttribute("style");
        card.style.position = "";
        old.replaceWith(next);
      })
    );
  }
  window.dashSettled = Promise.allSettled(drawing);
}

//: What the drawn grid was drawn from: a visit with the same answer refreshes
//: in place rather than starting again.
function dashGridShape(layout) {
  return JSON.stringify([layout.order, layout.hidden, layout.wide, dashEditMode, entriesEverLoaded && !allEntries.length]);
}

async function renderDashboard({ refresh = false } = {}) {
  // The saved layout lives in preferences, after a page reload this can run
  // before startApp has fetched them. `loadPreferences` (settings-panes.js) is the shared
  // reader: the cache if it is filled, otherwise the request already in flight,
  // which on a cold start is startApp's own. It used to be a second
  // `GET /preferences` here, and the dashboard is the first tab, so a cold
  // start made it every time (WORLD_CLASS_PLAN A2).
  //: The catalogue (app-features.js) loads beside the preferences, for Quick access.
  lazyScript("/js/app-features.js");
  await loadPreferences().catch(() => null);
  renderDashboardGreeting();
  renderQuickLinks();
  renderDashMore();
  wireDashDensity();
  renderFirstStepsLazy();
  const grid = $("dash-grid");
  const layout = dashLayout();
  const shape = dashGridShape(layout);
  //: Not while a full draw is still filling: its settle is what shows the grid.
  if (refresh && grid.dataset.shape === shape && grid.querySelector(".dash-widget") && !grid.classList.contains("dash-filling")) {
    refreshDashWidgets(grid);
    return;
  }
  grid.dataset.shape = shape;
  grid.replaceChildren();
  //: Unseen while its widgets draw and their spans settle, then faded in
  //: whole (`dashSettled` below; `.dash-filling`, 08-consistency.css).
  grid.classList.add("dash-filling");
  $("dash-editbar").classList.toggle("hidden", !dashEditMode); // only while editing
  const drawing = [];

  // A brand-new notebook filled this grid with a dozen cards each politely
  // saying it had nothing to show. Every message was fine on its own; together
  // they made a working app look broken on the day someone starts using it.
  // No widgets until there is anything to show, which is the first note; the
  // first steps above the grid say what to do instead (`renderFirstStepsLazy`).
  // `entriesEverLoaded` and not just the length: before the first GET /entries
  // comes back these are indistinguishable, and guessing "empty" paints the
  // brand-new-notebook card over a notebook full of notes.
  //: The one widget that needs no notes stays (unslop 1103, 20): the first screen was
  //: 349px of nothing under the steps, and Quick capture is the first thing to do.
  const bare = entriesEverLoaded && !allEntries.length && !dashEditMode;

  for (const name of layout.order) {
    const hidden = layout.hidden.includes(name);
    if (hidden && !dashEditMode) continue;
    if (bare && name !== "capture") continue;

    const widget = DASH_WIDGETS[name];
    const isWide = layout.wide.includes(name);
    const card = document.createElement("section");
    card.className =
      "card dash-widget" + (hidden ? " dash-hidden" : "") + (isWide ? " wide" : "");
    card.dataset.widget = name;

    const header = document.createElement("div");
    header.className = "row space-between";
    const title = document.createElement("h2");
    setLabel(title, widget.title);
    header.appendChild(title);
    if (dashEditMode) {
      const controls = document.createElement("span");
      //: **One line, whatever the zoom** (owner, 2026-11-11: "make sure the
      //: wrapping and ui issues arent an issue anywhere else from zoom or
      //: resolution"). Remove, Wide, Move earlier, Move later and Drag sat
      //: side by side at 293px, so 34 of 35 heads wrapped at 1366 (32px head
      //: became 66) and the row ran 5px past the card. The row-actions
      //: recipe (DESIGN.md): the first action stays, the rest fold into the
      //: head's ⋯, and Remove and the grip are their glyphs (with the words
      //: "Remove", 10 of 35 titles were cut at 1366), so the title gives way
      //: with an ellipsis only when long (`.dash-edit-actions`,
      //: 01-forms-settings.css).
      controls.className = "entry-actions dash-edit-actions";
      title.title = title.textContent.trim();
      // There used to be two width buttons here, side by side: one writing
      // to `wide` and one to the legacy `sizes` map. dashLayout() only falls
      // back to `sizes` when `wide` is empty, so the legacy button appeared to
      // work exactly once and then silently stopped. One control, one place
      // it's stored.
      controls.appendChild(
        smallButton(hidden ? "ph:plus" : "ph:x", hidden ? "Add this widget to the dashboard" : "Remove this widget from the dashboard", async () => {
          await toggleDashWidgetHidden(name);
          renderDashboard();
        })
      );
      //: **Reordering without a mouse.** HTML5 drag-and-drop is unreachable
      //: by keyboard, unusable with a screen reader and awkward on a
      //: trackpad, so Move earlier and Move later do the same job from the
      //: head's ⋯, and are the faster way to move one widget three places up.
      if (!hidden) {
        const at = layout.order.indexOf(name);
        const move = (delta) => async () => {
          const order = [...layout.order];
          const to = at + delta;
          if (to < 0 || to >= order.length) return;
          order.splice(to, 0, ...order.splice(at, 1));
          await saveDashLayout({ ...dashLayout(), order });
          renderDashboard();
          //: Focus follows the widget, so a second press moves the same card
          //: again rather than whatever landed under the pointer.
          setTimeout(() => {
            document.querySelector(`[data-widget="${name}"] .dash-edit-actions .kebab-opener`)?.focus();
          }, 60);
        };
        const items = [
          {
            label: isWide ? "ph:rows Narrow" : "ph:arrows-out-line-horizontal Wide",
            title: isWide ? "Show in one column" : "Span two columns",
            run: async () => {
              await toggleDashWidgetWide(name);
              renderDashboard();
            },
          },
        ];
        if (at > 0) items.push({ label: "ph:arrow-up Move earlier", title: "Move this widget earlier", run: move(-1) });
        if (at < layout.order.length - 1) items.push({ label: "ph:arrow-down Move later", title: "Move this widget later", run: move(1) });
        controls.appendChild(kebabMenu(items, "Widget layout options"));
      }
      const handle = document.createElement("span");
      handle.className = "drag-handle";
      handle.title = "Drag to move";
      const grip = document.createElement("i");
      grip.className = "ph ph-dots-six-vertical";
      grip.setAttribute("aria-hidden", "true");
      handle.append(grip);
      controls.appendChild(handle);
      header.appendChild(controls);
    }
    card.appendChild(header);

    const body = document.createElement("div");
    body.className = "dash-body";
    card.appendChild(body);
    if (!hidden) {
      // Promise.resolve() so a synchronous renderer can't break the whole
      // dashboard loop, and a throwing one only spoils its own card.
      drawing.push(mountWidgetBody(widget, body));
    }

    // Drag to reorder (edit mode only).
    if (dashEditMode) {
      card.draggable = true;
      card.addEventListener("dragstart", () => {
        dragWidget = name;
        card.classList.add("dragging");
      });
      card.addEventListener("dragend", async () => {
        card.classList.remove("dragging");
        dragWidget = null;
        // Persist whatever order the DOM ended up in.
        const order = [...grid.querySelectorAll(".dash-widget")].map(
          (el) => el.dataset.widget
        );
        await saveDashLayout({ ...dashLayout(), order });
      });
      card.addEventListener("dragover", (e) => {
        e.preventDefault();
        if (!dragWidget || dragWidget === name) return;
        const dragged = grid.querySelector(`[data-widget="${dragWidget}"]`);
        if (!dragged) return;
        dashDragOverCard(e, card, dragged, grid);
      });
    }
    grid.appendChild(card);
  }
  // Pack them once the cards exist; the observer keeps it right as the
  // async widget bodies fill in.
  grid.classList.remove("spans-ready");
  watchDashWidgets();
  //: **When the widgets have drawn** (INBOX 577): each fills after its own
  //: fetch and the grid's spans follow their heights, so the first seconds
  //: of a full dashboard moved its cards about (layout shift 0.12 seen
  //: after the opening curtain had lifted, smooth1005-boot.js on 300 notes).
  //: The opening curtain waits for this (`curtainShell`), 1.2s at most.
  //: Every visit, not only the first: a switch back to the dashboard redrew
  //: the widgets the same way, in view (0.26 on 300 notes, measured).
  const settled = (window.dashSettled = Promise.race([Promise.allSettled(drawing), new Promise((resolve) => setTimeout(function dashSettleTimeout() { resolve(); }, 1200))]));
  //: Placed a frame on (INBOX 1591): it reads the grid's box, and read here it laid the whole
  //: page out inside the script that delivered the notes (46ms at 4x); in the frame callback
  //: that layout is the one the frame was going to do anyway. Two frames on, the settle takes
  //: it down, so it is always up before then.
  let outline = null;
  afterFrames(() => {
    if (window.dashSettled === settled && grid.classList.contains("dash-filling")) outline = dashFillingSkeleton(grid, drawing.length);
  }, 1);
  settled.then(() => afterFrames(() => {
    if (window.dashSettled !== settled) return;
    sizeDashWidgets();
    grid.classList.remove("dash-filling");
    dashFillingSkeletonDone(outline);
  }));
}

//: `fn` once `count` animation frames have passed: the first has painted what
//: was just changed. The one frame loop for "after it has drawn" in this file
//: (tests/test_frontend_wake_sources.py counts them).
function afterFrames(fn, count = 2) {
  requestAnimationFrame(() => (count > 1 ? afterFrames(fn, count - 1) : fn()));
}

//: **While the grid fills unseen, its outline shows** (INBOX 596, the owner:
//: "some skeleton loaders are missing like on the dashboard"). The grid is
//: hidden until its widgets settle (`.dash-filling`, so the cards do not move
//: about in view), which left the page under the greeting empty for up to
//: 1.2s. In its place, cards of `.skeleton` in the grid's own columns, laid
//: over the same box, fading as the grid fades in. Inline styles through the
//: CSSOM because the boot stylesheets are at their cap.
function dashFillingSkeleton(grid, count) {
  document.querySelector(".dash-grid-skeleton")?.remove();
  const host = grid.offsetParent;
  if (!count || !host) return null;
  const cs = getComputedStyle(grid);
  const outline = document.createElement("div");
  outline.className = "dash-grid-skeleton";
  outline.setAttribute("aria-hidden", "true");
  const columns = Math.max(1, cs.gridTemplateColumns.split(" ").length);
  //: Every read before the first write: the append below dirties the layout, and `grid.offsetTop` read after it
  //: laid the page out a second time (86ms at 4x CPU on 1,200 notes, INBOX 1591). The outline is absolute, so
  //: the grid does not move for it.
  const top0 = grid.offsetTop;
  Object.assign(outline.style, {
    position: "absolute",
    left: `${grid.offsetLeft}px`,
    top: `${top0}px`,
    width: `${grid.offsetWidth}px`,
    maxHeight: `${Math.max(0, innerHeight - grid.getBoundingClientRect().top)}px`,
    overflow: "hidden",
    display: "grid",
    gridTemplateColumns: cs.gridTemplateColumns,
    gap: cs.rowGap === "normal" ? "var(--space-4)" : `${cs.rowGap} ${cs.columnGap}`,
    pointerEvents: "none",
    transition: "opacity var(--motion-base) var(--ease-out)",
  });
  for (let i = 0; i < Math.min(count, columns * 2); i++) outline.appendChild(tabSkeletonPiece({ height: "12rem" }));
  host.appendChild(outline);
  //: Follows the grid while it waits: Quick access and the greeting above it
  //: fill in after this is placed and push the grid down, which left the
  //: placeholder over them with their text showing through (owner,
  //: 2026-10-12). Cheap: two reads and two writes a frame for a second.
  //: By `translate`, which the compositor moves without a layout: writing
  //: `top` here counted as 0.077 of layout shift at boot.
  //: Read after a paint (INBOX 1419): in a timer it landed while the widgets
  //: filling in had left the layout dirty, and each read laid the page out.
  const follow = () => {
    if (!outline.isConnected) return;
    afterFrames(() => setTimeout(function dashSkeletonFollowTask() {
      if (!outline.isConnected) return;
      outline.style.translate = `0 ${grid.offsetTop - top0}px`;
      setTimeout(follow, 80);
    }, 0), 1);
  };
  setTimeout(follow, 80);
  return outline;
}

function dashFillingSkeletonDone(outline) {
  if (!outline) return;
  outline.style.opacity = "0";
  setTimeout(() => outline.remove(), 260);
}

// --- widget picker modal ------------------------------------------------------------
// A dedicated "Widgets" surface (roadmap §26) alongside the inline "Edit
// layout" mode: not a replacement for it. Both read/write the same
// `dashboard_layout` preference through dashLayout()/saveDashLayout() and the
// toggleDashWidget* helpers above; this modal just gives ~17 widgets a
// searchable, browsable list instead of only being reachable by scrolling
// the live grid in edit mode.

//: **A row here is a widget's *state*, not a pair of verbs.**
//:
//: Asked for: "the widgets menu and edit need a redesign". Three things were
//: wrong, and each is a semiotics problem rather than a styling one:
//:
//: 1. Wide was a **flip-label button**, it read "Wide" when narrow and
//:    "Narrow" when wide. A flip label says what pressing it will do and, at
//:    rest, says nothing about what the widget *is*; with nineteen rows you
//:    could not scan the list and see which ones span two columns. It is a
//:    two-state property, so it is now a toggle that stays pressed, with
//:    `aria-pressed` for anyone not looking at it.
//: 2. Remove sat at the same visual weight as Wide, so a destructive action
//:    and a reversible one looked identical. Remove keeps its own accent.
//: 3. **Order could only be changed by dragging the live grid**, unreachable
//:    by keyboard, and invisible from the one screen that lists every widget.
//:    Each row on the dashboard now carries move-up/move-down.
function dashWidgetToggle(label, title, pressed, onClick) {
  const button = smallButton(label, title, onClick);
  button.setAttribute("aria-pressed", String(pressed));
  button.classList.toggle("active", pressed);
  return button;
}

async function moveDashWidget(name, delta) {
  const layout = dashLayout();
  //: Reordered against the *visible* row order, not the full list: moving a
  //: widget "up" past three hidden ones looks like nothing happening.
  const visible = layout.order.filter((n) => !layout.hidden.includes(n));
  const from = visible.indexOf(name);
  const to = from + delta;
  if (from < 0 || to < 0 || to >= visible.length) return;
  visible.splice(to, 0, ...visible.splice(from, 1));
  //: Hidden widgets keep their relative places by being appended after: they
  //: are not on the dashboard, so their order is not something the user is
  //: looking at, and preserving it means un-hiding one puts it back where it
  //: was rather than at the end.
  layout.order = [...visible, ...layout.order.filter((n) => layout.hidden.includes(n))];
  await saveDashLayout(layout);
  renderDashboard();
  renderDashWidgetsList($("dash-widgets-search").value);
}

function dashWidgetRow(name, layout, position = null) {
  const widget = DASH_WIDGETS[name];
  const hidden = layout.hidden.includes(name);
  const isWide = layout.wide.includes(name);

  const row = document.createElement("div");
  row.className = "dash-widget-row";
  row.dataset.widget = name;

  const main = document.createElement("div");
  main.className = "dash-widget-row-main";
  const title = document.createElement("div");
  title.className = "dash-widget-row-title";
  setLabel(title, widget.title);
  main.appendChild(title);
  if (widget.description) {
    const desc = document.createElement("p");
    desc.className = "dash-widget-row-desc muted";
    desc.textContent = widget.description;
    main.appendChild(desc);
  }
  row.appendChild(main);

  //: **One toggle and one icon cluster, not four boxes.** Reported as one of
  //: two dialogs that are off the modal recipe. Measured before this, on a
  //: dialog listing twenty-four widgets: four controls a row, every one of
  //: them drawing its own resting tint, so the picker rendered 96 tinted
  //: boxes and read as a wall of buttons rather than as a list of widgets.
  //: That is the "everything is a button" complaint in one surface.
  //:
  //: The shape now: "Wide" stays a labelled toggle, because it is a property
  //: of the widget and its state has to be readable without hovering, and the
  //: three verbs (up, down, add/remove) become one icon cluster at the row's
  //: end. Add/remove loses its word and keeps its name: `smallButton` puts the
  //: title on `aria-label`, so it is still announced, and the icon already
  //: carries the meaning (plus against x) that the word repeated.
  const controls = document.createElement("div");
  controls.className = "dash-widget-row-controls entry-actions";
  if (!hidden) {
    controls.appendChild(
      dashWidgetToggle(
        "ph:arrows-out-line-horizontal Wide",
        isWide ? "Spanning two columns: press to narrow" : "Span two columns",
        isWide,
        async () => {
          await toggleDashWidgetWide(name);
          renderDashboard();
          renderDashWidgetsList($("dash-widgets-search").value);
        },
      ),
    );
  }
  const cluster = document.createElement("div");
  cluster.className = "dash-widget-row-cluster";
  if (!hidden && position) {
    //: Only where they can do something: the first row's "up" and the last
    //: row's "down" are disabled rather than absent, so the control cluster
    //: keeps one width and the rows stay aligned down the list.
    const up = smallButton("ph:arrow-up", "Move up", () => moveDashWidget(name, -1));
    up.disabled = position.index === 0;
    const down = smallButton("ph:arrow-down", "Move down", () => moveDashWidget(name, 1));
    down.disabled = position.index === position.total - 1;
    for (const button of [up, down]) button.classList.add("icon-button");
    cluster.append(up, down);
  }
  const onOff = smallButton(
    hidden ? "ph:plus" : "ph:x",
    hidden ? "Add this widget to the dashboard" : "Remove this widget from the dashboard",
    async () => {
      await toggleDashWidgetHidden(name);
      renderDashboard();
      renderDashWidgetsList($("dash-widgets-search").value);
    },
  );
  onOff.classList.add("icon-button");
  //: The one row that takes something away says so in the app's own danger
  //: colour, rather than looking like the reversible toggle beside it.
  if (!hidden) onOff.classList.add("danger");
  cluster.appendChild(onOff);
  controls.appendChild(cluster);
  row.appendChild(controls);
  return row;
}

// Two groups, "On your dashboard" and "Available", rather than a single
// list with a per-row status chip: with ~17 widgets, seeing at a glance how
// many are already on the dashboard is more useful than reading each row.
//: Which shelf each widget belongs on. A map here rather than a `group:` field
//: on all twenty-five entries: the catalogue's rows are already long, and a
//: widget's *group* is a fact about this list rather than about the widget.
//: Anything unlisted falls into "other", so a widget added later still appears
//:, silently vanishing from the picker is the one failure this must not have.
const DASH_WIDGET_GROUPS = {
  stats: "overview", streak: "overview", heatmap: "overview", pace: "overview", week: "overview",
  digest: "overview", art: "overview",
  pinned: "notes", random: "notes", categories: "notes", "on-this-day": "notes",
  unfinished: "notes", orphans: "notes", tensions: "notes", boards: "notes",
  documents: "notes",
  capture: "doing", reminders: "doing", focus: "doing", questions: "doing",
};

const DASH_WIDGET_GROUP_LABELS = {
  overview: "How the notebook is going",
  notes: "Your notes and what is in them",
  doing: "Things to do here",
  other: "Everything else",
};

//: What the dashboard currently is, in one line, and the way back to the
//: default. A list of twenty-five toggles with no statement of the result is a
//: list you edit blind, and "reset" is the answer to the fear that stops
//: people trying any of them.
function dashWidgetsSummary(layout) {
  const row = document.createElement("div");
  row.className = "row space-between dash-widgets-summary";
  const count = layout.order.filter((name) => !layout.hidden.includes(name)).length;
  const total = Object.keys(DASH_WIDGETS).length;
  const line = document.createElement("span");
  line.className = "muted";
  line.textContent = `${count} of ${total} on your dashboard`;
  row.appendChild(line);
  const reset = smallButton(
    "ph:arrow-counter-clockwise Reset layout",
    "Put every widget back to the order and visibility it started with",
    async () => {
      const sure = await confirmDialog(
        "Reset the dashboard layout?\n\nEvery widget goes back to its original place, and the ones you removed come back. Nothing else changes.",
      );
      if (!sure) return;
      //: An empty layout is what `dashLayout()` reads as "no preference", so
      //: this is a reset rather than a second copy of the default order kept
      //: in a place that could drift from the real one.
      await saveDashLayout({ order: [], hidden: [], wide: [], sizes: {} });
      renderDashboard();
      renderDashWidgetsList($("dash-widgets-search")?.value || "");
    },
  );
  row.appendChild(reset);
  return row;
}

function renderDashWidgetsList(filterText = "") {
  const container = $("dash-widgets-list");
  container.replaceChildren();
  const layout = dashLayout();
  container.appendChild(dashWidgetsSummary(layout));
  const q = filterText.trim().toLowerCase();
  const names = Object.keys(DASH_WIDGETS).filter((name) => {
    if (!q) return true;
    //: **The description is searched too.** Reported: "I just want a better
    //: menu and way to manage the widgets." With twenty-five of them, a filter
    //: that only matches titles means you have to already know a widget is
    //: called "Rediscover" to find the one that shows you an old note, which
    //: is exactly backwards, because the reason you are in this list is that
    //: you do not know what is in it.
    const widget = DASH_WIDGETS[name];
    const haystack = `${widget.title.replace(PH_LABEL, "")} ${widget.description || ""}`;
    return haystack.toLowerCase().includes(q);
  });

  const addGroup = (label, list, ordered) => {
    if (!list.length) return;
    const heading = document.createElement("h4");
    heading.className = "dash-widgets-group-label";
    heading.textContent = `${label} (${list.length})`;
    container.appendChild(heading);
    list.forEach((name, index) => {
      //: Position is the *unfiltered* one: with a search term typed, "up"
      //: still means one place up the dashboard, not one place up the four
      //: rows that happen to match.
      const position = ordered
        ? { index: ordered.indexOf(name), total: ordered.length }
        : null;
      container.appendChild(dashWidgetRow(name, layout, position));
    });
  };
  //: The dashboard's own order, so the list reads top-to-bottom the way the
  //: page does: a picker that lists widgets in a different order from the
  //: thing it is editing makes "move up" unreadable.
  const onDashboard = layout.order.filter((n) => !layout.hidden.includes(n));
  addGroup(
    "On your dashboard",
    onDashboard.filter((n) => names.includes(n)),
    onDashboard,
  );
  //: **The rest, grouped by what they are for.** Thirteen hidden widgets in one
  //: flat list called "Available" is a wall: you scroll it once, take nothing
  //: in, and close the dialog. Four short groups are four decisions.
  const available = names.filter((n) => layout.hidden.includes(n));
  for (const [group, label] of Object.entries(DASH_WIDGET_GROUP_LABELS)) {
    addGroup(
      label,
      available.filter((n) => (DASH_WIDGET_GROUPS[n] || "other") === group),
      null,
    );
  }

  if (!names.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No widgets match that search.";
    container.appendChild(empty);
  }
}

// --- Wave J: the notebook constellation ----------------------------------------------
//: **Its code is dash-art.js, fetched with the widget** (INBOX 1530 d, audit 1031
//: row 21): the sketch, its draw and p5's loader were boot bytes for one card.
//: `renderArtWidget` is a stand-in (lazy-entries.js); these two do nothing
//: until it has drawn, because nothing is on screen to stop or recolour.
function stopArt() {
  window.dashArtStop?.();
}
function refreshArtForTheme() {
  window.dashArtRefresh?.();
}
//: A colour chosen while the dashboard is showing redraws it, after the frames
//: (INBOX 1516: asked by its class, not by `checkVisibility`, a layout flush
//: that was billed to the list's `loadCategories` continuation).
document.addEventListener("categorycolours", () => {
  if (!$("tab-dashboard")?.classList.contains("hidden")) afterFrames(renderDashboard);
});


// Capture streak (Wave K): consecutive days up to today with at least
// one note, read from the same per-day series the stats strip uses.
//: **One streak rule for the whole dashboard, and it is the journal's.**
//: `daily_journal` (api/routes_entries.py) counts back from today and allows
//: today to be empty: nine days running and nothing yet this morning is a
//: streak of nine, not zero, or the number drops at every midnight and
//: comes back when you write, a counter that punishes the morning. The
//: greeting, the figures strip and the Streak widget each counted their own
//: and stopped at an empty today: measured at one in the morning after an
//: evening of 22 notes, "0 day streak" and "No streak yet" beside a journal
//: that said 1 (tests/test_dashboard_streak.py). `perDay` runs oldest to
//: newest, the last entry being today.
function dashStreak(perDay) {
  const days = perDay || [];
  let i = days.length - 1;
  if (i >= 0 && !(days[i] > 0)) i -= 1;
  let streak = 0;
  for (; i >= 0 && days[i] > 0; i -= 1) streak += 1;
  return streak;
}

//: Brief 89, and INBOX 1318 for Stats and Streak (the owner: "view the
//: status popup from the stats widget and other related widgets as well like
//: the streak"): each counting widget opens the Statistics page.
function dashStatsButton(id) {
  const button = smallButton("ph:chart-bar Statistics", "Open the Statistics page", () => openStatistics());
  button.id = id;
  return button;
}

async function renderStreakWidget(body) {
  const stats = await fetchDashStats();
  const perDay = stats.per_day || []; // oldest → newest, last = today

  const current = dashStreak(perDay);
  let longest = 0;
  let run = 0;
  for (const count of perDay) {
    run = count > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
  }

  const big = document.createElement("p");
  big.className = "dash-big";
  setLabel(big, current > 0 ? `ph:flame ${current}-day streak` : "No streak yet");
  body.appendChild(big);

  const sub = document.createElement("p");
  sub.className = "muted";
  if (current > 0) {
    //: A streak kept alive by yesterday says what keeps it going.
    const today = perDay.length ? perDay[perDay.length - 1] : 0;
    sub.textContent =
      `You've captured ${nounCount(current, "day")} running` +
      (today ? "" : ". Save a note today to keep it") +
      (longest > current ? ` · best in the last fortnight: ${longest}` : "");
  } else {
    sub.textContent = "Save a note today to start one.";
  }
  body.append(sub, dashStatsButton("streak-statistics"));
}

async function renderStatsWidget(body) {
  const stats = await fetchDashStats();
  const total = document.createElement("p");
  total.className = "dash-big";
  total.textContent = nounCount(stats.total_entries, "note");
  body.appendChild(total);

  // Last-14-days activity strip (theme colours, height = volume).
  const strip = document.createElement("div");
  strip.className = "activity-strip";
  strip.title = "Notes captured per day, last 14 days";
  const peak = Math.max(1, ...stats.per_day);
  for (const count of stats.per_day) {
    const bar = document.createElement("span");
    bar.style.height = `${Math.max(8, (count / peak) * 34)}px`;
    bar.classList.toggle("empty", count === 0);
    bar.title = nounCount(count, "note");
    strip.appendChild(bar);
  }
  body.appendChild(strip);

  const cats = document.createElement("div");
  cats.className = "entry-meta";
  for (const category of stats.categories.slice(0, 5)) {
    cats.appendChild(chip(`${category.name} · ${category.count}`, "", () => showCategoryNotes(category.name)));
  }
  strip.addEventListener("click", () => openStatistics());
  body.append(cats, dashStatsButton("stats-statistics"));
}
// Shared by the Pinned/Most-used/Recent-notes dashboard widgets, reported
// directly for Most Used, but all three shared the same gap: `notePreviewText`
// *strips* markdown syntax down to plain readable text (no literal `**`), which
// isn't the same as *rendering* it, `**bold**` read as clean but unstyled
// "bold", not actual bold text, and an inline image showed nothing at all.
// `renderInlineMarkdown`'s own `compact` mode is exactly what a label-sized
// list row already uses everywhere else in this app for the same reason
// (link chips, the document sidebar), swap to it here too rather than the
// stripped-text path.
// First image in a note's raw markdown, if it has one and the URL is safe to
// load. `renderInlineMarkdown`'s `compact` mode (used below) deliberately
// swaps every image for its alt text, right for a label-sized chip, but a
// dashboard row has room for the real picture, so this widget-only path
// pulls the first one out for a thumbnail instead.
const FIRST_MD_IMAGE = /!\[([^\]\n]{0,200})\]\(([^)\n]{1,500})\)/;
function firstNoteImage(content) {
  const m = FIRST_MD_IMAGE.exec(content || "");
  if (!m) return null;
  const [, alt, url] = m;
  return isRenderableUrl(url) ? { alt, url } : null;
}

//: **An attached picture is a picture too.** Reported: "the widgets and other
//: things dont render attached files on notes like the recently added widget
//: and other areas in the application."
//:
//: The gap is in the model, not the markup: an image *embedded* in the note
//: text is `![](…)` and was found by `firstNoteImage` above, but an image
//: **attached** to the note (`entry.attachments`, its own table, `/files/{id}`)
//: appears nowhere in the note's markdown: so a note whose only picture was
//: attached rather than pasted rendered as a row of text with no picture at
//: all, in every widget, forever.
function noteRowImage(entry) {
  const embedded = firstNoteImage((entry.content || "").replace(/\[\[([^[\]]{1,120})\]\]/g, "$1"));
  //: A picture at another address is never requested (audit 1029 N7), here as in the card.
  if (embedded && !isRemoteImage(embedded.url)) return embedded;
  const attached = (entry.attachments || []).find((file) => file.is_image);
  return attached ? { alt: attached.filename || "", url: `/files/${attached.id}` } : null;
}

// The non-image half of `noteRowImage`, a note's attached PDF, spreadsheet
// or the like has nothing to thumbnail, and previously had nothing shown
// for it at all here: `miniEntryList` only ever asked `noteRowImage`, so a
// note whose only attachment was a document rendered as if it were bare
// text, indistinguishable from a note with nothing attached. Reported
// directly: "files dont render in the widgets and other areas notes are
// shown."
function noteRowFile(entry) {
  const attached = (entry.attachments || []).find((file) => !file.is_image);
  return attached ? { name: attached.filename || "", url: `/files/${attached.id}` } : null;
}

function miniEntryList(body, entries, emptyText, emptyAction = null) {
  if (!entries.length) {
    if (emptyText) dashEmpty(body, emptyText, emptyAction);
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "dash-list";
  for (const entry of entries) {
    const li = document.createElement("li");
    li.dataset.obj = `note:${entry.id}`;
    // The wiki-link unwrap notePreviewText also did, renderInlineMarkdown
    // itself doesn't know `[[...]]`, only the full note-body renderer does.
    //: A `---` properties block is never the note's words (stripFrontmatter).
    const raw = stripFrontmatter(entry.content || "").replace(/\[\[([^[\]]{1,120})\]\]/g, "$1");
    const image = noteRowImage(entry);
    if (image) {
      li.classList.add("dash-has-thumb");
      const thumb = document.createElement("img");
      thumb.src = mediaSrc(image.url);
      thumb.alt = image.alt || "";
      thumb.loading = "lazy";
      thumb.className = "dash-list-thumb";
      li.appendChild(thumb);
    }
    const file = !image && noteRowFile(entry);
    const textEl = document.createElement("span");
    textEl.className = "dash-list-text";
    // Block syntax first. renderInlineMarkdown is exactly that, INLINE, so a
    // note beginning "# Groceries" rendered the hash as literal text, which is
    // the reported "markdown still isn't rendering" on these widgets: the bold
    // and italics worked and the headings, bullets and quote marks did not, so
    // it looked like nothing was rendering at all.
    //
    // The first line becomes the row's title instead of being flattened into
    // the preview, the same shape the timeline card uses. It is what a person
    // calls the note, and without it every row in a widget starts with the
    // same three words of body text.
    const flat = raw.replace(/^\s*(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+\.\s+)/gm, "").trim();
    const split = flat.indexOf("\n");
    const heading = (split === -1 ? flat : flat.slice(0, split)).trim();
    const rest = split === -1 ? "" : flat.slice(split + 1).replace(/\s+/g, " ").trim();

    if (heading) {
      const title = document.createElement("span");
      title.className = "dash-list-title";
      const cut = safeMdSlice(heading, 70);
      renderInlineMarkdown(title, cut.text, [], true);
      if (cut.truncated) title.appendChild(document.createTextNode("…"));
      textEl.appendChild(title);
    }
    if (rest) {
      const preview = document.createElement("span");
      preview.className = "dash-list-preview";
      const cut = safeMdSlice(rest, 110);
      renderInlineMarkdown(preview, cut.text, [], true);
      if (cut.truncated) preview.appendChild(document.createTextNode("…"));
      textEl.appendChild(preview);
    }
    if (file) {
      const chipEl = fileChip(file.name, file.url);
      chipEl.classList.add("dash-list-file-chip");
      textEl.appendChild(chipEl);
    }
    li.appendChild(textEl);
    li.title = "Open this note";
    li.addEventListener("click", () => flashEntry(entry.id));
    //: A row that opens on a click opens on Enter and Space too, as the
    //: boards widget's rows below do (INBOX 446 (5), axe's
    //: "scrollable region must have keyboard access" on Recently added):
    //: nothing in the list could take focus, so a keyboard could neither
    //: open a note from the widget nor scroll it.
    li.tabIndex = 0;
    li.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target === li) {
        e.preventDefault();
        flashEntry(entry.id);
      }
    });
    ul.appendChild(li);
  }
  body.appendChild(ul);
}

// GET /entries pages now (ENTRIES_PAGE_SIZE) rather than returning the whole
// notebook: these three widgets used to each fetch their own full copy of
// it independently, which silently would have started missing tags/notes
// past the first page on a large notebook. `allEntries` is the same data,
// already loaded by loadEntries() before any tab (including the dashboard)
// renders, and complete once its own background paging finishes, so
// preferring it is both a correctness fix and three fewer network calls.
// The fetch fallback only matters if a widget somehow renders before that
// first load, and mirrors the pattern renderRandomNoteWidget already uses.
async function renderPinnedWidget(body) {
  const entries = (await dashEntries()).filter((e) => e.pinned);
  miniEntryList(body, entries.slice(0, 5), "Star a note and it shows up here.", { label: "ph:note Open Notes", run: "tab", tab: "notes" });
}

async function renderMostOpenedWidget(body) {
  const entries = await apiJson("/most-opened", { cacheMs: 30000 });
  miniEntryList(body, entries, "Open a few notes and the ones you return to show here.", { label: "ph:note Open Notes", run: "tab", tab: "notes" });
}

async function renderReviewWidget(body) {
  const queue = await apiJson("/review-queue?limit=5", { cacheMs: 30000 });
  if (!queue.count) {
    dashEmpty(body, "Nothing to check: every filing is settled.", { label: "ph:note Open Notes", run: "tab", tab: "notes" });
    return;
  }
  const line = document.createElement("p");
  line.className = "dash-review-count";
  line.textContent = `${nounCount(queue.count, "note")} to check`;
  const open = smallButton("ph:checks Review them", "Show them in Notes, filtered to is:review", async () => {
    await switchTab("notes");
    showNotesSection("browse");
    const box = $("note-search");
    if (box) {
      box.value = "is:review";
      box.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  body.append(line, open);
}

async function renderMostUsedWidget(body) {
  const entries = await apiJson("/entries/most-accessed", { cacheMs: 30000 });
  miniEntryList(body, entries, "Ask questions and your most-used notes appear here.", { label: "ph:chat-circle Ask a question", run: "ask", tab: "chat" });
}

// The graph tab already knows how connected every note is (edges from
// EntryLink rows plus reply threads), this just ranks by how many of those
// edges touch each note, rather than asking the user to eyeball the graph
// for its own densest cluster. Perplexity brainstorm doc review flagged the
// gap: a "most-linked notes / hub" widget was one of the few ideas the app
// didn't already have a version of.
async function renderMostLinkedWidget(body) {
  const [entries, data] = await Promise.all([
    dashEntries(),
    fetchDashGraph().catch(() => null),
  ]);
  const degree = new Map();
  for (const edge of data?.edges || []) {
    if (typeof edge.source === "number") degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    if (typeof edge.target === "number") degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
  }
  const byId = new Map(entries.map((e) => [e.id, e]));
  const ranked = [...degree.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([id]) => byId.get(id))
    .filter(Boolean)
    .slice(0, 6);
  miniEntryList(body, ranked, "Link notes to each other and the most-connected ones show up here.", { label: "ph:link Find links to add", run: "suggest-links" });
}

async function renderRecentNotesWidget(body) {
  //: Not a map's topics (UX-06): a map of forty listed forty one-word rows.
  const entries = (await dashEntries()).filter((e) => !e.map_topic);
  const newest = [...entries].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );
  miniEntryList(body, newest.slice(0, 6), "Your newest notes will appear here.", { label: "ph:plus New note", run: "capture" });
}

async function renderTopTagsWidget(body) {
  const entries = await dashEntries();
  const counts = new Map();
  for (const entry of entries) {
    for (const tag of entry.tags || []) counts.set(tag, (counts.get(tag) || 0) + 1);
  }
  if (!counts.size) {
    dashEmpty(body, "Tag some notes and your top tags show up here.", { label: "ph:tag Show untagged notes", run: "untagged" });
    return;
  }
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  const cloud = document.createElement("div");
  cloud.className = "entry-meta";
  for (const [tag, count] of top) {
    const tagChip = chip(`${tag} · ${count}`, "tag", () => filterNotesByTag(tag));
    tagChip.title = `Show notes tagged “${tag}”`;
    cloud.appendChild(tagChip);
  }
  body.appendChild(cloud);
}

async function renderQuestionsWidget(body) {
  const questions = await apiJson("/chat/recent", { cacheMs: 30000 });
  if (!questions.length) {
    dashEmpty(body, "Your recent questions will appear here.", { label: "ph:chat-circle Ask a question", run: "ask", tab: "chat" });
    return;
  }
  const box = document.createElement("div");
  box.className = "recent";
  for (const question of questions) {
    const chipEl = chip(question.length > 40 ? question.slice(0, 39) + "…" : question, "", () => {
      switchTab("chat");
      sendChatMessage(question);
    });
    chipEl.title = question;
    box.appendChild(chipEl);
  }
  body.appendChild(box);
}

// Weekly digest caching (Wave J follow-up). The AI digest is expensive,
// so once it's generated it STAYS until you regenerate, and it resets
// itself each day. Generation is a module-level promise, so switching
// away from the dashboard never cancels it, whenever it finishes, the
// result is cached and shown next time the widget is on screen.
const DIGEST_KEY = "digestCache";
let digestPromise = null; // the in-flight generation, shared across renders

function todayStamp() {
  return new Date().toISOString().slice(0, 10);
}

function loadDigestCache() {
  try {
    const cached = prefs.json(DIGEST_KEY, null);
    if (cached && cached.date === todayStamp()) return cached.text; // fresh today
  } catch {
    /* corrupt cache: ignore and regenerate */
  }
  return null;
}

// Kicks off (or reuses) one generation. Caches the result for today,
// unless the server says it isn't cacheable (e.g. Ollama was offline).
// Streams the digest, calling onDelta with each chunk so the widget can show
// words as they arrive rather than a spinner. Resolves with the full text.
function generateDigest(onDelta) {
  if (!digestPromise) {
    digestPromise = streamDigest(onDelta)
      .then((result) => {
        if (result.cacheable !== false) {
          prefs.set(
            DIGEST_KEY,
            JSON.stringify({ text: result.text, date: todayStamp() })
          );
        }
        return result.text;
      })
      .finally(() => {
        digestPromise = null;
      });
  }
  return digestPromise;
}

async function streamDigest(onDelta) {
  const response = await api("/insights/digest/stream", { method: "POST" });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let text = "";
  let cacheable = true;
  // NDJSON: one JSON object per line, same shape as the chat stream.
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      let event;
      try {
        event = JSON.parse(line);
      } catch {
        continue; // a partial line: the next chunk completes it
      }
      if (event.type === "answer") {
        text += event.delta;
        if (onDelta) onDelta(text);
      } else if (event.type === "answer_final") {
        //: The server took a greeting or an announcement off the digest
        //: (`routes_insights`, `trim_assistant_padding`). The words already
        //: drawn are replaced once, and the trimmed text is what is cached.
        text = event.text || text;
        if (onDelta) onDelta(text);
      } else if (event.type === "done") {
        cacheable = event.cacheable !== false;
      }
    }
  }
  return { text, cacheable };
}


async function renderDigestWidget(outer) {
  const dayBox = document.createElement("div");
  const body = document.createElement("div");
  outer.replaceChildren(dayBox, body);
  //: Awaited at the end, not dropped (dashcls-1031): the widget counted as
  //: drawn while the day's lines were still in flight, so a revisit swapped in
  //: a 119px body that grew to 259px a fetch later and pushed every card below.
  const dayDrawn = renderDayDigest(dayBox);
  //: **The week under its own label, its source as a footnote** (the owner, 2026-11-04: "clicking
  //: generate this week's digest only shows the line, from your notes, no ai"). The week was all
  //: there, under the card's fold, and its first line was the source caption at body size, so the
  //: one line in view read as the whole answer. Now "This week" labels it, the caption is a muted
  //: footnote, and a click scrolls the card to the week.
  const weekParts = (text) => {
    const source = "From your notes.";
    const trimmed = String(text || "").trimStart();
    return trimmed.startsWith(source) ? { words: trimmed.slice(source.length).trimStart(), source } : { words: trimmed, source: "" };
  };
  const weekHead = () => {
    const head = document.createElement("p");
    head.className = "eyebrow";
    head.textContent = "This week";
    return head;
  };
  const toWeek = (head) => {
    for (let el = body.parentElement; el && el !== document.body; el = el.parentElement) {
      if (el.scrollHeight > el.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(el).overflowY)) {
        el.scrollTop += head.getBoundingClientRect().top - el.getBoundingClientRect().top;
        return;
      }
    }
  };
  const showDigest = (text, scroll = false) => {
    const { words, source } = weekParts(text);
    const head = weekHead();
    const out = document.createElement("div");
    renderMarkdown(out, words);
    const note = document.createElement("small");
    note.className = "muted";
    note.textContent = source;
    const controls = document.createElement("div");
    controls.className = "row";
    controls.appendChild(
      smallButton("ph:arrows-clockwise Regenerate", "Rebuild this week's digest now", () => {
        prefs.remove(DIGEST_KEY);
        runGeneration();
      })
    );
    body.replaceChildren(...[head, out, source ? note : null, controls].filter(Boolean));
    if (scroll) toWeek(head);
  };

  const runGeneration = () => {
    const thinking = document.createElement("p");
    thinking.className = "muted";
    setLabel(thinking, "ph:spin Thinking about your week…");
    body.replaceChildren(thinking);
    // Live-render the text as it streams in; the ring stays until the first
    // token arrives, then the words take over.
    const live = document.createElement("div");
    const liveHead = weekHead();
    let started = false;
    generateDigest((soFar) => {
      if (!body.isConnected) return;
      renderMarkdown(live, weekParts(soFar).words);
      if (!started) {
        started = true;
        body.replaceChildren(liveHead, live);
        toWeek(liveHead);
      }
    })
      .then((text) => {
        // The widget may have been left/re-rendered while we waited, 
        // only paint if this exact body is still on screen.
        if (body.isConnected) showDigest(text, true);
      })
      .catch((error) => {
        if (!body.isConnected) return;
        const retry = smallButton("ph:sparkle Generate this week's digest", "", runGeneration);
        body.replaceChildren(retry);
        toast(error.message, true);
      });
  };

  const cached = loadDigestCache();
  if (cached !== null) {
    showDigest(cached); // today's digest, kept until you regenerate
  } else if (digestPromise) {
    runGeneration(); // one is already running (from before a tab switch)
  } else {
    //: Never gated on a model (owner-1026b K3): with none, the server
    //: composes the week from the notes' own rows (`activity.week`), and a
    //: model, once on, writes the next one.
    //: Ghost: the Dashboard has one filled button, Save in Quick capture
    //: (unslop 1103, 11: two at once, 208x32 and 58x32).
    const generate = smallButton("ph:sparkle Generate this week's digest", "", runGeneration);
    body.append(generate);
  }
  await dayDrawn;
}

//: **The Notes tab's composer, here** (INBOX 1592, the owner: "like the quick capture section at the
//: top of your notes page"). The card is a copy of that tab's bar (`captureBar`, notes-list.js) and
//: opens in place into the same card (capture-card.js): Note, To-do, Draw, pictures, colour, tags,
//: Ctrl+Enter, one draft and one save path. A redraw while it is open hands it to the new bar.
async function renderQuickCaptureWidget(body) {
  const bar = document.createElement("div");
  bar.className = "capture-bar";
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "Add a note");
  const row = SURFACES.peek("notes", "capture-bar-row").cloneNode(true);
  //: No ids on the copy (two bars on one page): the card finds a bar by class.
  for (const el of [row, ...row.querySelectorAll("[id]")]) el.removeAttribute("id");
  bar.append(row);
  body.append(captureBar(bar));
}

async function renderRemindersWidget(body) {
  // To the end before filtering: taking four open ones out of a first page
  // that happens to be all done would show "no open reminders" to someone who
  // has plenty.
  const reminders = (await dashReminders()).filter((r) => !r.done).slice(0, 4);
  if (!reminders.length) {
    dashEmpty(body, "No open reminders.", { label: "ph:plus Add a reminder", run: "reminder", tab: "reminders" });
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "dash-list";
  for (const reminder of reminders) {
    const li = document.createElement("li");
    const due = new Date(reminder.due_at);
    //: The day and the time a person would say, never a machine timestamp
    //: with seconds ("9/24/2026, 1:22:17 PM", measured); the relative phrase
    //: ("in 23 hours") is the tooltip.
    const when = due.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", ...clockOptions() });
    //: The thing to do, then when, on a line of its own in the muted rank:
    //: "Submit IT assignment: Thu, Sep 24, 1:22 PM" as one run-on line made
    //: the time read as part of the sentence.
    const what = document.createElement("span");
    what.className = "dash-reminder-text";
    what.textContent = reminder.text;
    const at = document.createElement("span");
    at.className = "dash-reminder-when muted";
    at.textContent = when;
    li.append(what, at);
    li.title = relativeWhen(reminder.due_at);
    if (due < new Date()) li.classList.add("overdue");
    li.addEventListener("click", () => switchTab("reminders"));
    ul.appendChild(li);
  }
  body.appendChild(ul);
}

// --- activity heatmap (a year of capture activity, GitHub-style) ------------

async function renderHeatmapWidget(body) {
  const data = await apiJson("/insights/heatmap").catch(() => null);
  if (!data) {
    body.textContent = "Couldn't load your activity.";
    body.classList.add("muted");
    return;
  }
  if (!data.total) {
    dashEmpty(body, "Save some notes and your activity shows up here.", { label: "ph:plus New note", run: "capture" });
    return;
  }

  const grid = document.createElement("div");
  grid.className = "heatmap";
  //: `overflow-x: auto` makes this a scroll container, and Chromium gives
  //: every scroll container a tab stop so a keyboard user can scroll it with
  //: the arrow keys. Measured with a Tab walk: focus lands here, and it was
  //: the one element on the dashboard a screen reader would announce as
  //: nothing at all. A scrollable region that takes focus needs a role and a
  //: name, so it announces as what it is rather than as a bare group.
  //:
  //: `role="img"`, not `group`: the 365 day cells carry `title` text each,
  //: and a group would have a screen reader walk all of them one at a time
  //: to reach the same story the summary line under the grid already tells
  //: in one sentence. This is a graphic drawn out of divs, so it announces
  //: as one, and the tab stop Chromium gives it still scrolls with arrows.
  grid.setAttribute("role", "img");
  grid.setAttribute("aria-label", `Activity over the last year, ${nounCount(data.total, "note")}`);
  //: axe `scrollable-region-focusable` (serious): the grid scrolls sideways
  //: and nothing in it takes focus. An explicit stop, with a ring below
  //: (`.heatmap:focus-visible`), so the arrow keys reach the older weeks.
  grid.tabIndex = 0;
  body.appendChild(grid);

  //: **Full size, full year, scrolled rather than shrunk.** The first
  //: version of this widget shrank its cells to fit whatever width the
  //: widget had (reported "the heatmap on the dashboard is a little
  //: small" at 2.7px cells), and the fix after that kept the cells at
  //: their real size by showing fewer weeks instead, so nothing ever
  //: scrolled. Reported again, 2026-09-09: "the whole thing fits into the
  //: small not wide dashboard, it looked better bigger and scrolled to the
  //: right" -- a year read a glance at a time is still the point, but the
  //: owner's own preference is the wider, scrollable shape over the
  //: cropped one, so this reverses the second fix and keeps the first: the
  //: whole year at `--heat-cell-max` (03-dashboard-widgets.css sets the
  //: grid's own columns to that width now, rather than a `1fr` this
  //: function used to divide up), the grid scrolls horizontally
  //: (`.heatmap`'s `overflow-x: auto`), and it opens scrolled to today
  //: (below) rather than to the oldest day, so the crop this replaces is
  //: not missed on first paint.
  function paint() {
    const counts = data.counts;
    const start = new Date(`${data.start}T00:00:00`);
    // Pad so each column is a whole week starting on Sunday, and the last one is whole too.
    const lead = start.getDay();
    const cells = [];
    for (let i = 0; i < Math.ceil((lead + counts.length) / 7) * 7; i++) {
      const cell = document.createElement("span");
      const index = i - lead;
      if (index < 0 || index >= counts.length) cell.className = "heat-cell heat-blank";
      else {
        const count = counts[index];
        // Five buckets, scaled against the busiest day so quiet notebooks still show contrast.
        cell.className = `heat-cell heat-${count === 0 ? 0 : Math.min(4, Math.ceil((count / data.busiest) * 4))}`;
        const day = new Date(start);
        day.setDate(day.getDate() + index);
        cell.title = `${day.toLocaleDateString()}, ${nounCount(count, "note")}`;
      }
      cells.push(cell);
    }
    //: **Opens at today by CSS alone** (INBOX 1578, then 1741). The grid is `direction: rtl`, so a
    //: scroll box starts at its right edge, and its columns run right to left: the weeks are
    //: appended newest first, which draws them oldest to newest, left to right. The end was read
    //: from the last cell's rect (a layout read of 13k nodes, 70ms at 4x) and re-taken on every
    //: refit; nothing reads it now, and a reader who scrolls away is simply left there.
    for (let w = cells.length - 7; w >= 0; w -= 7) grid.append(...cells.slice(w, w + 7));
  }
  paint();

  const legend = document.createElement("div");
  legend.className = "heat-legend muted";
  const less = document.createElement("span");
  less.textContent = "Less";
  legend.appendChild(less);
  for (let level = 0; level <= 4; level++) {
    const swatch = document.createElement("span");
    swatch.className = `heat-cell heat-${level}`;
    legend.appendChild(swatch);
  }
  const more = document.createElement("span");
  more.textContent = "More";
  legend.appendChild(more);
  body.appendChild(legend);

  const summary = document.createElement("p");
  summary.className = "muted";
  //: The busiest day is a date with its count ("10 March, 4 notes"), not a bare
  //: number that reads as a number of days (sweep 1028b W15).
  const top = new Date(`${data.start}T12:00:00`);
  top.setDate(top.getDate() + data.counts.indexOf(data.busiest));
  const busiest = data.busiest ? ` · busiest day ${top.toLocaleDateString(undefined, { day: "numeric", month: "long" })} (${nounCount(data.busiest, "note")})` : "";
  summary.textContent = `${nounCount(data.total, "note")} in the last year${busiest}`;
  //: Brief 89 (statistics row 1): the page is one click from here, the
  //: grid itself and the button below, where it was three (Settings,
  //: General, What you use).
  const stats = dashStatsButton("heatmap-statistics");
  grid.addEventListener("click", () => openStatistics());
  //: In a row so the button is its own width beside the line, not a bar.
  const foot = document.createElement("div");
  foot.className = "row";
  foot.append(summary, stats);
  body.appendChild(foot);
}

// --- category breakdown ------------------------------------------------------

async function renderCategoriesWidget(body) {
  const stats = await fetchDashStats().catch(() => null);
  const categories = (stats && stats.categories) || [];
  if (!categories.length) {
    dashEmpty(body, "Save a few notes and your categories appear here.", { label: "ph:plus New note", run: "capture" });
    return;
  }
  const max = categories[0].count || 1;
  const list = document.createElement("div");
  list.className = "cat-bars";
  for (const { name, count } of categories.slice(0, 8)) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "cat-row";
    row.title = `Show the ${name} notes`;
    const label = document.createElement("span");
    label.className = "cat-name";
    label.textContent = name;
    const track = document.createElement("span");
    track.className = "cat-track";
    const fill = document.createElement("span");
    fill.className = "cat-fill";
    //: Accent unless the person gave this category a colour.
    const chosen = categoryColour(name);
    if (chosen) fill.style.setProperty("--cat-fill", chosen);
    fill.style.width = `${Math.max(6, (count / max) * 100)}%`;
    track.appendChild(fill);
    const num = document.createElement("span");
    num.className = "cat-count";
    num.textContent = count;
    row.append(label, track, num);
    row.addEventListener("click", () => showCategoryNotes(name));
    list.appendChild(row);
  }
  body.appendChild(list);
  //: The review queue's size (WORLD_CLASS_PLAN section 17, row 1): the
  //: filings Atlas was unsure of or left in Uncategorised, with the way in.
  const waiting = (stats && stats.to_review) || 0;
  if (!waiting) return;
  const line = document.createElement("p");
  line.className = "muted night-questions";
  line.textContent = `${nounCount(waiting, "note")} to check where ${waiting === 1 ? "it was" : "they were"} filed.`;
  const open = smallButton("ph:check-square Review filings", "The Notes list, filtered to the filings to check", () => showNotesFilter("is:review"));
  const review = document.createElement("div");
  //: The night widget's question line is the same shape: one recipe, no new rule.
  review.className = "row night-questions-row";
  review.append(line, open);
  body.appendChild(review);
}

// A plain char-count slice can land inside an unclosed `![alt](url` or
// `[text](url`, the truncated tail then has no closing `)`, so INLINE_MD
// never matches it and it prints as literal markdown source instead of
// rendering (or vanishing) as intended. Reported live as "the Rediscover
// widget doesn't render images or sketches", plausible root cause: a
// sketch note is a caption plus `![...](...)`, and the reference is exactly
// what a mid-string cut most often lands inside. Backs the cut up to just
// before the last unclosed `[`/`![` before the limit, if there is one.
function truncateMarkdownSafe(text, limit) {
  if (text.length <= limit + 1) return text;
  let cut = limit;
  const openBracket = text.lastIndexOf("[", cut);
  if (openBracket !== -1) {
    const closeParen = text.indexOf(")", openBracket);
    if (closeParen === -1 || closeParen >= cut) {
      cut = text[openBracket - 1] === "!" ? openBracket - 1 : openBracket;
    }
  }
  return text.slice(0, cut).trimEnd() + "…";
}

// --- rediscover a random note ------------------------------------------------

async function renderRandomNoteWidget(body) {
  // **Scored, not random, once there is enough notebook to score.**
  // WORLD_CLASS_PLAN 15, I4: a notebook that only ever shows you what you
  // just wrote is a diary, and the thing a notebook can do that a pile of
  // files cannot is bring back the note you would never have thought to look
  // for. The backend (`ai/resurface.py`) ranks by three facts a person can
  // check, age, links and opens, and this is the surface the plan asks for.
  //
  // The random pick below is kept, not replaced, and it is the right answer
  // for a small notebook: `MIN_NOTEBOOK` in resurface.py refuses to rank at
  // all under ten notes, because "the three most faded" out of five notes is
  // the same three for ever, which teaches people to ignore the panel. So
  // `/resurface` answers with nothing there and this falls through to the
  // shuffle, which is what that size actually wants.
  const cards = await apiJson("/resurface?limit=3", { silent: true, cacheMs: 30000 }).catch(() => null);
  const items = (cards && cards.items) || [];
  if (items.length) {
    paintFadedNotes(body, items);
    return;
  }
  await renderRandomShuffle(body);
}

// Three notes slipping out of reach, each with the reason it was chosen and
// a way to say "never again". The dismissal is a correction
// (`POST /learned/corrections`), the same store the filing and search
// corrections use, so sending a card away is a decision the notebook keeps
// rather than a thirty-second reprieve.
function paintFadedNotes(body, items) {
  body.replaceChildren();
  const list = document.createElement("div");
  list.className = "faded-list";
  for (const item of items) {
    const card = document.createElement("div");
    card.className = "faded-card";

    const main = document.createElement("div");
    main.className = "faded-main";
    const title = document.createElement("button");
    title.type = "button";
    title.className = "linklike faded-title";
    title.textContent = noteNamePlain(item.title || "") || "Untitled note";
    //: One line, ellipsised, so the full title is the tooltip; the reason
    //: line beneath is what the row is for.
    title.title = `${title.textContent}: open in the Notes tab`;
    title.addEventListener("click", () => flashEntry(item.id));
    main.appendChild(title);

    if (item.reason) {
      const why = document.createElement("p");
      why.className = "muted faded-why";
      // The facts, not the score: "120 days old, no links, never opened" is
      // checkable and "0.82" is not.
      why.textContent = item.reason;
      main.appendChild(why);
    }
    card.appendChild(main);

    //: Icon-only, in its own column: the label "Never again" under a
    //: three-line title put every row's control at a different height and
    //: the widget read as a stack of uneven blocks (INBOX 216). The words
    //: stay as the name and the tooltip.
    const dismiss = smallButton("ph:x", "Never again: stop showing this note here", async () => {
      dismiss.disabled = true;
      try {
        const said = { kind: "dismiss_resurface", subject: { entry_id: item.id } };
        const made = await apiJson("/learned/corrections", { method: "POST", body: JSON.stringify(said) });
        pushCorrectionUndo("Hid a note from Rediscover", said, made, () => renderRandomNoteWidget(body));
        card.remove();
        // Emptied by dismissals: ask again rather than leaving a blank panel,
        // the next three are already ranked.
        if (!list.querySelector(".faded-card")) renderRandomNoteWidget(body);
      } catch (error) {
        dismiss.disabled = false;
      }
    });
    dismiss.classList.add("faded-dismiss");
    card.appendChild(dismiss);
    list.appendChild(card);
  }
  body.appendChild(list);
}

async function renderRandomShuffle(body) {
  const entries = await loadSurface(body, "your notes", dashEntries);
  if (!entries) return;
  if (!entries.length) {
    dashEmpty(body, "Save some notes and one will resurface here.", { label: "ph:plus New note", run: "capture" });
    return;
  }

  // "Another" has to actually show another one.
  //
  // Reported as broken, and it was: the pick was uniform over every note
  // WITH REPLACEMENT, so it could hand back the note already on screen and
  // the click did nothing. That is not rare, it is 1 in N, so a tenth of
  // clicks on a ten-note notebook, half of them on two notes, and every
  // single one when there is only one note to show. Excluding the current
  // note makes the button keep its promise.
  let current = null;

  const paint = () => {
    body.replaceChildren();
    const pool = entries.filter((e) => e.id !== (current && current.id));
    const note = (pool.length ? pool : entries)[
      Math.floor(Math.random() * (pool.length || entries.length))
    ];
    current = note;
    // Rendered as markdown, like every other place a note's text is shown.
    // It was `textContent`, so a note written with a heading, a list or any
    // emphasis surfaced here as its raw source, `## Schedule` and `**bold**`
    // spelled out: which makes the one widget whose whole job is to make an
    // old note appealing show it at its least readable.
    //
    // A <div>, not a <p>: renderMarkdown appends block elements, and a <p>
    // containing a <ul> is invalid markup that browsers fix by closing the
    // paragraph early, which drops the styling this class carries.
    const text = document.createElement("div");
    text.className = "random-note";
    renderMarkdown(text, truncateMarkdownSafe(stripFrontmatter(note.content), 239));
    body.appendChild(text);

    // A sketch's picture is never in `note.content` at all: the sketch pad
    // saves a caption as the note's text and the drawing as a real
    // Attachment (saveSketch), a completely different mechanism from a
    // pasted/dropped image's inline `![](...)`. Any renderer that only
    // reads content, this one included, showed nothing for a sketch note, 
    // "the widget doesn't render... sketches", reported directly. Same
    // .attachment-thumb treatment the note-card list already gives an
    // attached image, so a sketch resurfaced here looks the way it does
    // everywhere else.
    const images = (note.attachments || []).filter((a) => a.is_image);
    if (images.length) {
      const row = document.createElement("div");
      row.className = "entry-links";
      for (const attachment of images) {
        const wrap = document.createElement("span");
        wrap.className = "thumb-wrap";
        const img = document.createElement("img");
        img.className = "attachment-thumb";
        img.alt = attachment.filename;
        img.title = `${attachment.filename}: click to view full size`;
        attachmentObjectUrl(attachment)
          .then((url) => (img.src = url))
          .catch(() => wrap.remove());
        img.addEventListener("click", () => {
          openLightbox(
            images.map((a) => ({ filename: a.filename, getUrl: () => attachmentObjectUrl(a), openUrl: `/files/${a.id}` })),
            images.indexOf(attachment)
          );
        });
        wrap.appendChild(img);
        row.appendChild(wrap);
      }
      body.appendChild(row);
    }

    const meta = document.createElement("div");
    meta.className = "entry-meta";
    meta.appendChild(chip(note.category || "Uncategorised", "tag"));
    const when = document.createElement("span");
    when.className = "entry-date";
    when.textContent = new Date(note.created_at).toLocaleDateString();
    meta.appendChild(when);
    body.appendChild(meta);

    const row = document.createElement("div");
    row.className = "row";
    const another = smallButton("ph:dice-five Another", "Show a different note", paint);
    if (entries.length < 2) {
      // There is no other note to show. A live-looking button that cannot do
      // anything is the exact shape of "this control is broken", say why
      // instead.
      another.disabled = true;
      another.title = "This is your only note so far, write another and it'll shuffle.";
    }
    row.appendChild(another);
    row.appendChild(
      smallButton("ph:note-pencil Open", "Open this note in the Notes tab", () => flashEntry(note.id))
    );
    body.appendChild(row);
  };
  paint();
}

// --- weighted tag cloud ------------------------------------------------------

async function renderTagCloudWidget(body) {
  const tags = await loadSurface(body, "your tag cloud", () => apiJson("/insights/tag-cloud"));
  if (!tags) return;
  if (!tags.length) {
    dashEmpty(body, "Tag some notes and your cloud grows here.", { label: "ph:tag Show untagged notes", run: "untagged" });
    return;
  }
  const max = tags[0].count || 1;
  const cloud = document.createElement("div");
  cloud.className = "tag-cloud";
  for (const { tag, count } of tags) {
    // Font size scales with frequency (0.8rem – 1.7rem).
    const weight = count / max;
    const item = chip(tag, "tag", () => filterNotesByTag(tag));
    item.style.fontSize = `${(0.8 + weight * 0.9).toFixed(2)}rem`;
    item.style.opacity = String(0.55 + weight * 0.45);
    item.title = `${nounCount(count, "note")} tagged “${tag}”`;
    cloud.appendChild(item);
  }
  body.appendChild(cloud);
}

// --- focus timer (dashboard widget) -----------------------------------------
// State lives at module level so it keeps running while the widget re-renders
// (e.g. when you switch away and back to the dashboard).
//
// **Redesigned** (UI_MODERNISATION V8, INBOX 829): a ring that empties as the
// time runs, the time large inside it; the lengths as one segmented control
// with a stepper for any other; Start and Pause one filled button; at the end
// a chime, a notification (the bell and the system's) and, when Breaks is on,
// a five-minute break that starts by itself; and today's focused minutes,
// kept per day in this browser.
//: `unsaved`: seconds focused since the last save to today's count, written
//: on every pause and end rather than every second.
let focusTimer = { remaining: 0, total: 25 * 60, running: false, mode: "focus", focusTotal: 25 * 60, unsaved: 0 };
const FOCUS_PRESETS = [5, 15, 25, 50, 60];
const FOCUS_BREAK_MIN = 5;
const FOCUS_SVG = "http://www.w3.org/2000/svg";
const FOCUS_RING_R = 52;

function focusTimeLabel(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

//: Seconds focused today, in this browser: "YYYY-MM-DD:seconds".
function focusTodaySeconds(add = 0) {
  const day = new Date().toLocaleDateString("en-CA");
  const [stored, seconds] = String(prefs.get("focusToday", "")).split(":");
  let total = stored === day ? Number(seconds) || 0 : 0;
  if (add) {
    total += add;
    prefs.set("focusToday", `${day}:${total}`);
  }
  return total;
}

function focusRing() {
  const svg = document.createElementNS(FOCUS_SVG, "svg");
  svg.setAttribute("viewBox", "0 0 120 120");
  svg.setAttribute("class", "focus-ring-svg");
  svg.setAttribute("aria-hidden", "true");
  for (const name of ["focus-ring-track", "focus-ring-fill"]) {
    const circle = document.createElementNS(FOCUS_SVG, "circle");
    circle.setAttribute("cx", "60");
    circle.setAttribute("cy", "60");
    circle.setAttribute("r", String(FOCUS_RING_R));
    circle.setAttribute("class", name);
    if (name === "focus-ring-fill") {
      circle.id = "focus-ring-fill";
      const length = 2 * Math.PI * FOCUS_RING_R;
      circle.setAttribute("stroke-dasharray", String(length));
    }
    svg.appendChild(circle);
  }
  return svg;
}

//: `root` is the widget's own body while it is being built: it is not in the
//: page yet, so `$()` found nothing and the ring and the time stayed empty
//: until something ticked (owner, 2026-10-12: "didnt properly load").
function paintFocusTimer(root = document) {
  const $ = (id) => root.querySelector(`#${id}`) || document.getElementById(id);
  const shown = focusTimer.remaining || focusTimer.total;
  const display = $("focus-timer-display");
  if (display) display.textContent = focusTimeLabel(shown);
  const mode = $("focus-ring-mode");
  if (mode) mode.textContent = focusTimer.mode === "break" ? "Break" : focusTimer.running || focusTimer.remaining ? "Focus" : `${Math.round(focusTimer.total / 60)} min`;
  const fill = $("focus-ring-fill");
  if (fill) {
    const length = 2 * Math.PI * FOCUS_RING_R;
    fill.style.strokeDashoffset = String(length * (1 - shown / focusTimer.total));
  }
  $("focus-ring")?.classList.toggle("is-break", focusTimer.mode === "break");
  const toggle = $("focus-timer-toggle");
  if (toggle) setLabel(toggle, focusTimer.running ? "ph:pause Pause" : focusTimer.remaining ? "ph:play Resume" : "ph:play Start");
  for (const button of root.querySelectorAll(".focus-presets-seg button")) {
    const chosen = focusTimer.mode === "focus" && Number(button.dataset.minutes) * 60 === focusTimer.focusTotal;
    button.setAttribute("aria-pressed", String(chosen));
    button.classList.toggle("active", chosen);
  }
  //: Not while it is being typed in: a repaint would put the old figure back under the caret.
  const step = $("focus-step-value");
  if (step && document.activeElement !== step) step.value = String(Math.round(focusTimer.focusTotal / 60));
  const today = $("focus-today");
  if (today) {
    const seconds = focusTodaySeconds() + focusTimer.unsaved;
    const minutes = Math.floor(seconds / 60);
    today.textContent = minutes ? `${minutes} min focused today` : seconds ? "Under a minute focused today" : "Nothing focused yet today";
  }
}

function focusTimerTick() {
  if (focusTimer.remaining > 0) {
    focusTimer.remaining -= 1;
    if (focusTimer.mode === "focus") focusTimer.unsaved += 1;
    paintFocusTimer();
    if (focusTimer.remaining === 0) focusTimerEnded();
  }
}

//: Two soft notes from Web Audio: no file to fetch, and quiet enough for a
//: library. The context is made here, after the Start press that allows it.
function focusChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [880, 660].forEach((hz, i) => {
      const tone = ctx.createOscillator();
      const gain = ctx.createGain();
      tone.frequency.value = hz;
      const at = ctx.currentTime + i * 0.35;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.2, at + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.6);
      tone.connect(gain).connect(ctx.destination);
      tone.start(at);
      tone.stop(at + 0.65);
    });
    setTimeout(() => ctx.close().catch(() => {}), 1500);
  } catch {
    // No Web Audio: the notification still says it.
  }
}

function focusTimerEnded() {
  stopFocusTimer();
  focusChime();
  const wasBreak = focusTimer.mode === "break";
  const minutes = Math.round(focusTimer.total / 60);
  const title = wasBreak ? "Break over" : `Focus session done: ${minutes} min`;
  const detail = wasBreak ? "Start the next session when you are ready." : `${Math.floor(focusTodaySeconds() / 60)} min focused today.`;
  notify("Tessellate", `${title}. ${detail}`);
  recordNotification({ kind: "task", title, detail, key: `focus:${Date.now()}` });
  toast(`${title}. ${detail}`);
  if (!wasBreak && prefs.bool("focusBreaks", false)) {
    focusTimer.mode = "break";
    focusTimer.total = FOCUS_BREAK_MIN * 60;
    focusTimer.remaining = 0;
    startFocusTimer();
    return;
  }
  focusTimer.mode = "focus";
  focusTimer.total = focusTimer.focusTotal;
  focusTimer.remaining = 0;
  paintFocusTimer();
}

function startFocusTimer() {
  if (focusTimer.running) return;
  if (focusTimer.remaining <= 0) focusTimer.remaining = focusTimer.total;
  focusTimer.running = true;
  askNotificationPermission();
  secondTick.add(focusTimerTick);
  paintFocusTimer();
}

function stopFocusTimer() {
  focusTimer.running = false;
  secondTick.remove(focusTimerTick);
  if (focusTimer.unsaved) {
    focusTodaySeconds(focusTimer.unsaved);
    focusTimer.unsaved = 0;
  }
  paintFocusTimer();
}

function setFocusTimer(minutes) {
  stopFocusTimer();
  focusTimer.mode = "focus";
  focusTimer.focusTotal = Math.max(1, Math.min(180, Math.round(minutes))) * 60;
  focusTimer.total = focusTimer.focusTotal;
  focusTimer.remaining = 0;
  paintFocusTimer();
}

//: The stepper: one minute at a time below 10, five at a time from there, 1 to 180.
//: `dir` is 1 for longer, -1 for shorter; from 12, shorter is 10 and longer is 15.
function focusStep(dir) {
  const now = Math.round(focusTimer.focusTotal / 60);
  let next;
  if (dir > 0) next = now < 10 ? now + 1 : (Math.floor(now / 5) + 1) * 5;
  else next = now <= 10 ? now - 1 : (Math.ceil(now / 5) - 1) * 5;
  setFocusTimer(Math.max(1, Math.min(180, next)));
}

// async to match the widget contract in renderDashboard (render() must
// return a promise).
async function renderFocusTimerWidget(body) {
  const ring = document.createElement("div");
  ring.id = "focus-ring";
  ring.className = "focus-ring";
  const face = document.createElement("div");
  face.className = "focus-ring-face";
  const mode = document.createElement("span");
  mode.id = "focus-ring-mode";
  mode.className = "focus-ring-mode";
  const display = document.createElement("div");
  display.id = "focus-timer-display";
  display.className = "focus-timer-display focus-ring-time";
  display.setAttribute("role", "timer");
  face.append(mode, display);
  ring.append(focusRing(), face);
  body.appendChild(ring);

  const presets = document.createElement("div");
  presets.className = "row focus-presets";
  const seg = document.createElement("div");
  seg.className = "seg focus-presets-seg";
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Session length");
  for (const mins of FOCUS_PRESETS) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.minutes = String(mins);
    button.textContent = `${mins}`;
    button.title = `${mins} minutes`;
    button.addEventListener("click", () => setFocusTimer(mins));
    seg.appendChild(button);
  }
  const stepper = document.createElement("div");
  stepper.className = "focus-stepper";
  stepper.setAttribute("role", "group");
  stepper.setAttribute("aria-label", "Any length");
  const value = document.createElement("input");
  value.id = "focus-step-value";
  value.type = "number";
  value.min = "1";
  value.max = "180";
  value.step = "1";
  value.inputMode = "numeric";
  value.className = "focus-step-value";
  value.setAttribute("aria-label", "Minutes, 1 to 180");
  value.title = "Type any length from 1 to 180 minutes";
  //: Typed minutes (any 1 to 180): a figure that is not one puts the current length back.
  const typed = () => {
    if (value.value.trim() === "" || !Number.isFinite(Number(value.value))) return paintFocusTimer();
    setFocusTimer(Number(value.value));
    value.value = String(Math.round(focusTimer.focusTotal / 60));
  };
  value.addEventListener("change", typed);
  value.addEventListener("keydown", (event) => {
    if (event.key === "Enter") typed();
  });
  const unit = document.createElement("span");
  unit.className = "muted focus-step-unit";
  unit.textContent = "min";
  stepper.append(
    smallButton("ph:minus", "Shorter: one minute below 10, else five", () => focusStep(-1)),
    value,
    unit,
    smallButton("ph:plus", "Longer: one minute below 10, else five", () => focusStep(1))
  );
  presets.append(seg, stepper);
  body.appendChild(presets);

  const controls = document.createElement("div");
  controls.className = "row focus-controls";
  const toggle = smallButton("ph:play Start", "Start or pause the timer", () => {
    if (focusTimer.running) stopFocusTimer();
    else startFocusTimer();
  }, false);
  toggle.id = "focus-timer-toggle";
  const reset = smallButton("ph:arrow-counter-clockwise", "Reset the timer", () => {
    focusTimer.remaining = 0;
    focusTimer.mode = "focus";
    focusTimer.total = focusTimer.focusTotal;
    stopFocusTimer();
  });
  reset.classList.add("quiet");
  const breaks = document.createElement("label");
  breaks.className = "check-row focus-breaks";
  breaks.title = `A ${FOCUS_BREAK_MIN}-minute break starts by itself after each session`;
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = prefs.bool("focusBreaks", false);
  box.addEventListener("change", () => prefs.set("focusBreaks", box.checked ? "1" : "0"));
  const words = document.createElement("span");
  words.textContent = "Breaks";
  breaks.append(box, words);
  controls.append(toggle, reset, breaks);
  body.appendChild(controls);

  const today = document.createElement("p");
  today.id = "focus-today";
  today.className = "muted focus-today";
  body.appendChild(today);

  //: The Clock's line and button (utility-tools.js, INBOX 1551), drawn when that module is in.
  ensureModule("utilities").then(() => utilityOps.focusRow(body));

  paintFocusTimer(body);
}

// --- wiring (moved out of app.js's own wiring block, §88.3) -----------------------
//
// These two listener groups used to sit inside app.js's general wiring, far
// from the code they drive (the same "scattered, not one block" shape the
// roadmap warned about). Moving only the function *definitions* out and
// leaving these `addEventListener` calls behind in app.js would have been
// the exact hazard documents.js's split found: `$("features-close")
// .addEventListener("click", closeFeatures)` passes `closeFeatures` as a
// bare identifier, resolved the moment this line runs, and this line runs
// at app.js's own top-level, parse-time pass, before dashboard.js (loaded
// after app.js) has defined it. Left behind, that throws `ReferenceError`
// and aborts the rest of app.js's synchronous top-level code, same as
// `initDocSidebarTabs()` did. The other listeners here wrap their calls in
// arrow functions, which resolve the name lazily at click time rather than
// at registration time, so they were never actually at risk, but keeping
// the whole related group together here is clearer than splitting it by
// which handlers happen to be safe.
//: Edit layout is a row of the dock's menu; Done is the edit line's own
//: button, the one way out of the mode, so it is the only place this id is.
onSurface("notes", () => {
  $("dash-edit").addEventListener("click", async () => {
    const leaving = dashEditMode;
    dashEditMode = !dashEditMode;
    //: The button just pressed is hidden with its line: the focus goes back to
    //: the menu it came from rather than to the page's body, once the render
    //: has rebuilt that menu (it replaces the opener).
    await renderDashboard();
    if (leaving) $("dash-more")?.querySelector("button")?.focus();
    //: The edit line is plain text (audit 1031 N28: a hidden `role=status` is read
    //: out when it later shows, and 25 such regions exist at once); the one
    //: status region says what began.
    else announce("Editing layout. Drag a card to move it, make it wide or narrow, or remove it. Done ends it.");
  });
});

// Widget picker modal (roadmap §26): a dedicated surface alongside "Edit
// layout" above, not a replacement for it.
$("dash-widgets-open").addEventListener("click", () => {
  $("dash-widgets-search").value = "";
  renderDashWidgetsList();
  $("dash-widgets-dialog").showModal();
});
$("dash-widgets-search").addEventListener("input", (e) => renderDashWidgetsList(e.target.value));
// Tools & features browser (opened from the dashboard quick links).
$("features-close").addEventListener("click", closeFeatures);
$("features-search").addEventListener("input", (e) => renderFeatures(e.target.value));
wireBackdropClose($("features-overlay"), () => closeFeatures());

// --- The four widgets for what the dashboard could not previously see -------
//
// Registered in DASH_WIDGETS above, where the reasoning for the set lives.
// All four follow the shape every widget here already uses: an async function
// taking the widget's own `body` element, reading `allEntries` or one cached
// `apiJson`, and rendering an empty state that says what to do rather than
// "no data".

/** A row that opens something other than a note, styled like `.dash-list`. */
function dashActionRow(ul, { title, meta, onOpen, hint, thumb, chip = null, obj = "" }) {
  const li = document.createElement("li");
  if (obj) li.dataset.obj = obj;
  if (thumb) {
    li.classList.add("dash-has-thumb");
    li.appendChild(thumb);
  }
  const text = document.createElement("span");
  text.className = "dash-list-text";
  //: `chip` stands in for the plain title when the row is a thing the app has
  //: a chip for: a mind map, so far. Not *beside* the title: the chip already
  //: carries the title, and drawing both would say the same words twice on one
  //: row. The chip passed here is the non-interactive form (`mapChip`'s own
  //: comment says why), because this `<li>` is already `role="button"`.
  const titleEl = chip || document.createElement("span");
  if (!chip) {
    titleEl.className = "dash-list-title";
    titleEl.textContent = title;
  }
  text.appendChild(titleEl);
  if (meta) {
    const metaEl = document.createElement("span");
    metaEl.className = "dash-list-preview";
    metaEl.textContent = meta;
    text.appendChild(metaEl);
  }
  li.appendChild(text);
  li.title = hint || "Open";
  // A row that does something is a control, so it answers to the keyboard and
  // announces itself as one, `li.addEventListener("click")` alone (the shape
  // `miniEntryList` uses) is invisible to a screen reader and unreachable by
  // Tab.
  li.tabIndex = 0;
  li.setAttribute("role", "button");
  //: A list holds only list items (WCAG 1.3.1); these rows are buttons, so the
  //: list is a group of them.
  if (!ul.hasAttribute("role")) ul.setAttribute("role", "group");
  const go = () => onOpen();
  li.addEventListener("click", go);
  li.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      go();
    }
  });
  ul.appendChild(li);
}

//: A widget with nothing to show is the empty-state recipe (DESIGN.md): one
//: sentence and one action (INBOX 464 (12): eleven were a sentence only).
//: `action` is `{ label, run, tab, sub }`: `run` is a `data-empty-action` the
//: delegated listener (navigation.js) knows, and `tab`/`sub` are where it
//: lives, which the listener opens first. `null` is a decided "nothing to do".
function dashEmpty(body, text, action) {
  const box = document.createElement("div");
  box.className = "empty-state dash-empty";
  const line = document.createElement("p");
  line.textContent = text;
  box.appendChild(line);
  if (action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    setLabel(button, action.label);
    button.dataset.emptyAction = action.run;
    if (action.tab) button.dataset.emptyTab = action.tab;
    if (action.sub) button.dataset.emptySub = action.sub;
    box.appendChild(button);
  }
  body.appendChild(box);
}

//: The Boards & maps widget lives in dash-boards.js, loaded on its first
//: draw (moved 2026-10-05 for the boot budget, INBOX 553(d)).
async function renderBoardsWidget(body) {
  if (await ensureModule("dashBoards")) await dashRenderBoards(body);
}

// --- While you were away: the night shift's morning card ---------------------
//
// WORLD_CLASS_PLAN 15, I1: "a 'While you were away' card on the Dashboard each
// morning ... each line opens a review list where every item is accept /
// dismiss / open the note". `GET /night/latest` is the card: the latest pass,
// what it found that is still visible, and the last pass that found anything
// when the latest found nothing, so a quiet night does not blank the morning.
// A line opens its review list in place (`GET /night/runs/{id}/facts`), paged,
// and each row's Dismiss is `DELETE /learned/{id}`, which also stops the same
// thing being worked out again. Accepting is keeping: there is nothing to
// press for a fact that is right.
const NIGHT_KIND_WORDS = {
  claim: ["claim", "claims"],
  question: ["open question", "open questions"],
  tension: ["claim that disagrees with another", "claims that disagree with others"],
  answered: ["question answered later", "questions answered later"],
  date: ["date it names", "dates it names"],
  entity: ["name it mentions", "names it mentions"],
  duplicate: ["note that repeats another", "notes that repeat others"],
};
const NIGHT_PAIR_LEAD = { tension: "Disagrees with", answered: "Answers" };
const NIGHT_PAGE = 5;







// --- Recent activity: the event feed, read with its cursor ---------------------
//
// `GET /events` reads forwards from a cursor (WORLD_CLASS_PLAN B1). The first
// render asks for the newest few with `tail`; every later render asks only for
// what came after the cursor it was handed, so reopening the dashboard reads
// the handful of new rows rather than the log again. No timer: the widget is
// redrawn when the dashboard is, and an idle tab polling a log for a strip
// nobody is looking at is the cost INBOX 266 (7) took out of this app.
const DASH_ACTIVITY_KINDS = "entry,document,board,reminder";
const DASH_ACTIVITY_ROWS = 8;
let dashActivity = { items: [], cursor: null };

const DASH_ACTIVITY_NOUNS = { entry: "Note", document: "Document", board: "Board", reminder: "Reminder" };

async function dashActivityItems() {
  const first = dashActivity.cursor === null;
  const path = first
    ? `/events?tail=${DASH_ACTIVITY_ROWS}&entity_type=${DASH_ACTIVITY_KINDS}`
    : `/events?since=${dashActivity.cursor}&entity_type=${DASH_ACTIVITY_KINDS}`;
  const feed = await apiJson(path, { silent: true });
  dashActivity = {
    items: [...dashActivity.items, ...(feed.items || [])].slice(-DASH_ACTIVITY_ROWS),
    cursor: feed.cursor ?? dashActivity.cursor ?? 0,
  };
  return dashActivity.items;
}

async function renderActivityWidget(body) {
  let items;
  try {
    items = await dashActivityItems();
  } catch {
    surfaceFailed(body, "your recent activity", () => renderActivityWidget(body));
    return;
  }
  if (!items.length) {
    dashEmpty(body, "What you and Atlas change in the notebook shows up here.", { label: "ph:plus New note", run: "capture" });
    return;
  }
  const entries = await dashEntries().catch(() => []);
  const byId = new Map(entries.map((entry) => [entry.id, entry]));
  const ul = document.createElement("ul");
  ul.className = "dash-list";
  for (const item of [...items].reverse()) {
    const entry = item.entity_type === "entry" || item.entity_type === "board" ? byId.get(item.entity_id) : null;
    const noun = DASH_ACTIVITY_NOUNS[item.entity_type] || "Item";
    const name = entry ? noteNamePlain(entry.content, 60) : "";
    const verb = HISTORY_ACTION_WORDS[item.action] || item.action.replace(/_/g, " ");
    //: A compacted run is one line, not a burst of edits (the feed's own
    //: `snapshot` count says how many it stands for).
    const run = item.snapshot ? ` (${item.snapshot} edits)` : "";
    const who = historyActorLabel(item.actor);
    const meta = [who, relativeTime(item.created_at)].filter(Boolean).join(" · ");
    const open = entry && !entry.is_deleted
      ? () => flashEntry(entry.id)
      : item.entity_type === "document" && item.action !== "deleted"
        ? () => {
            switchTab("documents");
            openDocument(item.entity_id);
          }
        : null;
    const title = `${verb}${run}: ${name || noun.toLowerCase()}`;
    if (open) {
      dashActionRow(ul, { title, meta, hint: `Open this ${noun.toLowerCase()}`, onOpen: open });
      continue;
    }
    //: Something that is gone (a note deleted for good, a reminder) has
    //: nothing to open, so it is a plain row rather than a button that does
    //: nothing, which is the "dead control" the vibe check counts.
    const li = document.createElement("li");
    //: The list is a `group` (`dashActionRow` makes it one for its button
    //: rows), so a plain row beside them is no list item: axe `listitem`
    //: (serious) fails an `li` whose parent is not a list.
    li.setAttribute("role", "presentation");
    const text = document.createElement("span");
    text.className = "dash-list-text";
    const titleEl = document.createElement("span");
    titleEl.className = "dash-list-title";
    titleEl.textContent = title;
    const metaEl = document.createElement("span");
    metaEl.className = "dash-list-preview";
    metaEl.textContent = meta;
    text.append(titleEl, metaEl);
    li.appendChild(text);
    ul.appendChild(li);
  }
  body.appendChild(ul);
  const undo = activityUndoControl(items, byId, () => {
    //: The undo wrote a `restored` event per note; the feed reads it on the
    //: next render through its cursor, so a fresh read shows it at once.
    body.replaceChildren();
    renderActivityWidget(body);
  });
  if (undo) body.appendChild(undo);
}

//: **Undo what Atlas did** (OPEN.md events-undo, `POST /events/undo`). The
//: activity list is where a change by Atlas, a skill or the auto-filer is
//: seen, so it is where it is taken back: one ghost button under the list per
//: actor that appears in it (a `kebabMenu` when there are several), undoing
//: that actor's changes from the oldest one shown. Always the dry run first,
//: shown as the confirm dialog's body (what goes back, what is left because
//: you changed it since, what cannot be undone), then the same plan applied.
function activityActorName(actor) {
  if (actor === "system:filing") return "the auto-filer";
  if (actor === "system:librarian") return "Atlas's background pass";
  if (actor.startsWith("ai:")) return `Atlas (${actor.slice(3).split("@")[0].replace(/_/g, " ")})`;
  return historyActorLabel(actor) || actor;
}

function activityUndoPlanText(plan, byId, name) {
  const undo = plan.items.filter((item) => item.status === "undo");
  const titled = undo.slice(0, 3).map((item) => {
    const entry = byId.get(item.entity_id);
    const first = entry ? noteNamePlain(entry.content, 40) : "";
    return first ? `“${first}”` : `note ${item.entity_id}`;
  });
  const more = undo.length > titled.length ? ` and ${undo.length - titled.length} more` : "";
  const lines = [
    `${undo.length} note${undo.length === 1 ? " goes" : "s go"} back to how ${undo.length === 1 ? "it was" : "they were"} before ${name} changed ${undo.length === 1 ? "it" : "them"}: ${titled.join(", ")}${more}.`,
  ];
  const since = plan.items.filter((item) => item.status === "changed since").length;
  if (since) lines.push(`${since} you changed since stay${since === 1 ? "s" : ""} as ${since === 1 ? "it is" : "they are"}.`);
  const cannot = plan.items.filter((item) => ["too old", "not undoable", "gone"].includes(item.status)).length;
  if (cannot) lines.push(`${cannot} can't be undone (a board item, or a change too old to have kept its values).`);
  return lines.join(" ");
}

async function undoActorFrom(actor, since, byId, rerender) {
  const name = activityActorName(actor);
  let plan;
  try {
    plan = await apiJson("/events/undo", { method: "POST", body: JSON.stringify({ actor, since }) });
  } catch (error) {
    toast(error.message || "Couldn't read what would be undone.", true);
    return;
  }
  const undoable = plan.items.filter((item) => item.status === "undo").length;
  if (!undoable) {
    const already = plan.items.every((item) => item.status === "already undone");
    toast(already ? `Already undone: nothing ${name} changed is left to put back.` : `Nothing ${name} changed can be put back from here.`);
    return;
  }
  const ok = await confirmDialog(
    `Undo what ${name} changed?\n\n${activityUndoPlanText(plan, byId, name)}`,
    { confirmLabel: "Undo", danger: false }
  );
  if (!ok) return;
  try {
    const done = await apiJson("/events/undo", {
      method: "POST",
      body: JSON.stringify({ actor, since, dry_run: false }),
    });
    toast(`Put back ${nounCount(done.undone, "note")}.`);
    await loadEntries().catch(() => {});
    rerender();
  } catch (error) {
    toast(error.message || `Couldn't undo what ${name} changed.`, true);
  }
}

//: Per actor that is not the person, the oldest shown entry event that no
//: undo has reversed yet: undo from just before it, so everything that actor
//: did in the list goes back. A `restored` event in the feed names the events
//: it reversed (`undid`), and those are skipped, so the row goes once an undo
//: has put everything back instead of staying to say "Already undone".
function activityUndoStarts(items) {
  const undone = new Set();
  for (const item of items) {
    if (item.action === "restored" && Array.isArray(item.undid)) item.undid.forEach((id) => undone.add(id));
  }
  const from = new Map();
  for (const item of items) {
    if (!item.actor || item.actor === "user" || item.actor.startsWith("system:recycle")) continue;
    if (item.entity_type !== "entry" || undone.has(item.id)) continue;
    const at = from.get(item.actor);
    if (at === undefined || item.id < at) from.set(item.actor, item.id);
  }
  return from;
}

function activityUndoControl(items, byId, rerender) {
  const from = activityUndoStarts(items);
  if (!from.size) return null;
  const row = document.createElement("div");
  row.className = "row activity-undo";
  const actors = [...from.keys()];
  if (actors.length === 1) {
    const [actor] = actors;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    setLabel(button, `ph:arrow-counter-clockwise Undo what ${activityActorName(actor)} did`);
    button.title = "See what would go back first";
    button.addEventListener("click", () => undoActorFrom(actor, from.get(actor) - 1, byId, rerender));
    row.appendChild(button);
    return row;
  }
  const menu = kebabMenu(
    actors.map((actor) => ({
      label: `ph:arrow-counter-clockwise Undo what ${activityActorName(actor)} did`,
      run: () => undoActorFrom(actor, from.get(actor) - 1, byId, rerender),
    })),
    "Undo what Atlas did"
  );
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = "Undo what Atlas did";
  row.append(label, menu);
  return row;
}

async function renderDocumentsWidget(body) {
  // `GET /documents` is already ordered by updated_at descending, so the
  // newest-edited are simply the first rows, no client-side sort needed.
  const docs = await apiJson("/documents", { cacheMs: 4000, silent: true }).catch(() => null);
  if (!docs || !docs.length) {
    dashEmpty(body, "Write or import a document and the ones you edited last show up here.", { label: "ph:plus New document", run: "new-document", tab: "library", sub: "library-view-docs" });
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "dash-list";
  for (const doc of docs.slice(0, 6)) {
    const words = doc.words ? `${doc.words.toLocaleString()} word${doc.words === 1 ? "" : "s"}` : "Empty";
    dashActionRow(ul, {
      title: doc.title || "Untitled document",
      obj: `document:${doc.id}`,
      meta: `${words} · ${relativeTime(doc.updated_at)}`,
      hint: "Open this document",
      onOpen: () => {
        switchTab("documents");
        openDocument(doc.id);
      },
    });
  }
  body.appendChild(ul);
}

//: `GET /bookmarks` is already "pinned first, then newest first"
//: (routes_bookmarks.py), the same order the Library tab itself opens with,
//: so this widget and that tab can never disagree about which bookmarks
//: count as "recent". Opens the site directly, in a new tab, the same as
//: clicking a bookmark's own title in the Library does: a bookmark's one
//: job is the page behind it, not a detour through the tab that lists it.
//: `bookmarkAddress` (library.js) is not called here on purpose: this
//: widget can render before Library's own script has ever loaded (the
//: dashboard is usually the first tab open), and `bookmark.title ||
//: bookmark.url` is the same fallback the bookmark-attach pickers already
//: use (app.js, documents.js) for exactly that reason.
async function renderBookmarksWidget(body) {
  const bookmarks = await apiJson("/bookmarks", { cacheMs: 4000, silent: true }).catch(() => null);
  if (!bookmarks || !bookmarks.length) {
    dashEmpty(body, "Save a link to a website you visit often and it will show up here.", { label: "ph:link-simple Add a bookmark", run: "add-link", tab: "library", sub: "library-view-links" });
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "dash-list";
  for (const bookmark of bookmarks.slice(0, 6)) {
    dashActionRow(ul, {
      title: bookmark.title || bookmark.url,
      meta: relativeTime(bookmark.created_at),
      hint: `Open ${bookmark.url}`,
      onOpen: () => window.open(safeHref(bookmark.url), "_blank", "noopener,noreferrer"),
    });
  }
  body.appendChild(ul);
}

//: A markdown task line: `- [ ]` / `* [x]` / `1. [ ]`, with the loose leading
//: whitespace real notes actually contain. Deliberately anchored per line
//: with `m` rather than scanning the whole body, so an indented sub-task
//: counts and a literal "[ ]" mid-sentence does not.
const DASH_OPEN_TASK = /^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[[ \t]\]/gm;
const DASH_DONE_TASK = /^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[[xX]\]/gm;

async function renderUnfinishedWidget(body) {
  const entries = await dashEntries();
  const withTasks = [];
  for (const entry of entries) {
    //: A list row holds a note's first 300 characters (INBOX 1525), so the server's counts of the whole text come first.
    const content = entry.content || "";
    if (entry.tasks_open == null && !content.includes("[")) continue; // cheap reject before two regexes
    // `lastIndex` is shared state on a `g` regex, so these must be reset per
    // note or every second note silently scores zero, the classic one.
    DASH_OPEN_TASK.lastIndex = 0;
    DASH_DONE_TASK.lastIndex = 0;
    const open = entry.tasks_open ?? (content.match(DASH_OPEN_TASK) || []).length;
    if (!open) continue;
    const done = entry.tasks_done ?? (content.match(DASH_DONE_TASK) || []).length;
    withTasks.push({ entry, open, done });
  }
  if (!withTasks.length) {
    dashEmpty(body, "Nothing outstanding. Checklists you write as “- [ ] something” appear here until they are ticked.", { label: "ph:plus New note", run: "capture" });
    return;
  }
  // Closest to finished first: a list with one box left is the one worth
  // showing, not the one someone has barely started.
  withTasks.sort((a, b) => a.open - b.open || b.done - a.done);
  const ul = document.createElement("ul");
  ul.className = "dash-list";
  for (const row of withTasks.slice(0, 6)) {
    const first = noteNamePlain(row.entry.content) || "Untitled note";
    const total = row.open + row.done;
    dashActionRow(ul, {
      title: first.replace(/^#{1,6}\s+/, "").slice(0, 70),
      meta: `${row.open} left of ${total}`,
      hint: "Open this note",
      onOpen: () => flashEntry(row.entry.id),
    });
  }
  body.appendChild(ul);
}



/**
 * The Tensions doorway.
 *
 * Explains the idea and opens the review; it does **not** run one. Every
 * other widget renders from `allEntries` or one cached fetch, and a widget
 * that quietly started a model pass over the notebook every time the
 * dashboard drew would be the most expensive thing on the page.
 */
async function renderTensionsWidget(body) {
  //: WORLD_CLASS_PLAN B4: what is already known comes from the derived
  //: tensions table (`GET /entries/tensions/known`), which no model is asked
  //: to fill: a scan's findings, the night shift's, and the pairs linked as
  //: contradicting. The review itself still runs only when asked.
  const [entries, known] = await Promise.all([
    dashEntries(),
    apiJson("/entries/tensions/known?limit=3", { silent: true }).catch(() => null),
  ]);
  const counts = (known && known.counts) || {};
  const pending = (known && known.tensions) || [];
  const accepted = counts.accepted || 0;

  const blurb = document.createElement("p");
  blurb.className = "muted";
  const linked = accepted ? `${accepted} linked as contradicting` : "";
  blurb.textContent = counts.open
    ? [`${nounCount(counts.open, "disagreement")} to look at`, linked].filter(Boolean).join(", ") + "."
    : accepted
      ? `${nounCount(accepted, "place")} where your notes contradict each other.`
      : "Nothing here can tell you where you changed your mind, until you look.";
  body.appendChild(blurb);

  if (pending.length) {
    const list = document.createElement("ul");
    list.className = "dash-list night-facts dash-tensions";
    const left = { n: counts.open || pending.length };
    const gone = () => {
      left.n -= 1;
      if (!list.children.length) {
        const done = document.createElement("p");
        done.className = "muted";
        done.textContent = left.n > 0 ? `${left.n} more in the review.` : "All decided.";
        list.replaceWith(done);
      }
    };
    for (const tension of pending) list.appendChild(dashTensionRow(tension, gone));
    body.appendChild(list);
  } else {
    const explain = document.createElement("p");
    explain.className = "muted dash-tension-explain";
    explain.textContent =
      "Your local model reads pairs of related notes for claims that can't both be right.";
    body.appendChild(explain);
  }

  const open = document.createElement("button");
  open.type = "button";
  open.className = "ghost small";
  const icon = document.createElement("i");
  icon.className = "ph ph-scales ph-lead";
  icon.setAttribute("aria-hidden", "true");
  open.append(icon, entries.length < 2 ? "Nothing to compare yet" : "Review disagreements");
  open.disabled = entries.length < 2;
  open.addEventListener("click", () => openSuggestionsInbox("tensions"));
  body.appendChild(open);
}

//: One known disagreement on the widget: the two notes by name, the reason,
//: and who found it when (B4's "computed by <model> at <ts>"), with the same
//: icon actions as the night card's rows: open either note, link them as
//: contradicting, or dismiss.
function dashTensionRow(tension, onGone) {
  const li = document.createElement("li");
  li.className = "night-fact";
  const text = document.createElement("span");
  text.className = "dash-list-text";
  const title = document.createElement("span");
  title.className = "dash-list-title night-fact-text";
  title.textContent = `${tension.earlier_title || "Untitled note"} and ${tension.later_title || "Untitled note"}`;
  const why = document.createElement("span");
  why.className = "dash-list-preview night-fact-pair";
  why.textContent = tension.explanation || "Linked as contradicting.";
  const meta = document.createElement("span");
  meta.className = "dash-list-preview";
  const who = tension.model === "local" ? "Found without a model" : tension.model === "person" ? "Linked by you" : `Found by ${tension.model}`;
  meta.textContent = [who, tension.computed_at ? relativeTime(tension.computed_at) : ""].filter(Boolean).join(" · ");
  text.append(title, why, meta);
  const actions = document.createElement("span");
  actions.className = "night-fact-actions";
  const button = (icon, label, run) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small icon-only";
    b.title = label;
    b.setAttribute("aria-label", label);
    setLabel(b, icon);
    b.addEventListener("click", run);
    return b;
  };
  const ids = JSON.stringify({ earlier_id: tension.earlier_id, later_id: tension.later_id });
  const decide = (path, done) => async (event) => {
    const pressed = event.currentTarget;
    pressed.disabled = true;
    try {
      const done = await apiJson(path, { method: "POST", body: ids });
      pushTensionLinkUndo(tension.earlier_id, tension.later_id, path.endsWith("/accept") ? "accept" : "dismiss", done?.created !== false);
      toast(done);
      li.remove();
      onGone();
    } catch (error) {
      pressed.disabled = false;
      toast(error.message || "Couldn't save that decision.", true);
    }
  };
  actions.append(
    button("ph:arrow-square-out", "Open the earlier note", () => flashEntry(tension.earlier_id)),
    button("ph:arrows-left-right", "Open the later note", () => flashEntry(tension.later_id)),
    button("ph:link", "Link the two notes as contradicting", decide("/entries/tensions/accept", "Linked as contradicting")),
    button("ph:x", "Not a contradiction", decide("/entries/tensions/dismiss", "Dismissed: this pair won't come back.")),
  );
  li.append(text, actions);
  return li;
}

//: **On this day.** A notebook accumulates, and the thing that makes years of
//: it worth having is being handed a page from one of them without asking.
//: Same date, earlier years and earlier months, months as well as years,
//: because a notebook two months old would otherwise never show anything and
//: an empty widget teaches you to remove it.
function renderOnThisDayWidget(body) {
  const now = new Date();
  const day = now.getDate();
  const month = now.getMonth();
  const thisYear = now.getFullYear();
  const entries = (typeof allEntries !== "undefined" ? allEntries : []).filter((entry) => {
    const at = new Date(entry.created_at);
    if (Number.isNaN(at.getTime())) return false;
    if (at.getDate() !== day) return false;
    //: A different year on the same date, or an earlier month this year. Today
    //: itself is excluded: "on this day" that returns what you wrote an hour
    //: ago is a mirror, not a memory.
    if (at.getFullYear() !== thisYear) return true;
    return at.getMonth() !== month;
  });
  if (!entries.length) {
    return dashEmpty(
      body,
      "Nothing from this date yet. What you write today comes back here next month.",
      { label: "ph:plus New note", run: "capture" },
    );
  }
  entries.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  //: Grouped by when, because "two years ago" is the fact that makes the row
  //: worth reading and a bare list of notes buries it.
  const seen = new Set();
  const shown = [];
  for (const entry of entries) {
    const at = new Date(entry.created_at);
    //: Counted in months: 10 November last year, seen on 10 October, is
    //: eleven months ago, not "1 year ago", and it used to take the year's
    //: one place from the note written on this very date (Brief 85).
    const months = (thisYear - at.getFullYear()) * 12 + month - at.getMonth();
    const years = months / 12;
    const when = Number.isInteger(years) ? `${nounCount(years, "year")} ago` : `${nounCount(months, "month")} ago`;
    if (seen.has(when)) continue;
    seen.add(when);
    shown.push({ entry, when });
    if (shown.length >= 4) break;
  }
  const list = document.createElement("ul");
  list.className = "dash-list";
  list.setAttribute("role", "group"); // rows are buttons (dashActionRow says why)
  for (const { entry, when } of shown) {
    const li = document.createElement("li");
    li.setAttribute("role", "button");
    li.tabIndex = 0;
    const stamp = document.createElement("span");
    stamp.className = "chip dash-onthisday-when";
    chipWords(stamp, when);
    const text = document.createElement("span");
    text.className = "dash-list-text";
    renderInlineMarkdown(text, noteLabel(entry, 90), null, true);
    li.append(stamp, text);
    const open = () => flashEntry(entry.id);
    li.addEventListener("click", open);
    li.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
    list.appendChild(li);
  }
  body.appendChild(list);
}

//: **Writing pace.** The streak widget answers "did I show up"; this answers
//: "did I write anything when I did", which is a different and more honest
//: question: a one-word note keeps a streak alive.
//:
//: A fortnight rather than a week: seven bars cannot show a trend, and a month
//: of bars in a widget column is a picket fence.
const DASH_PACE_DAYS = 14;

function renderPaceWidget(body) {
  const entries = typeof allEntries !== "undefined" ? allEntries : [];
  const days = [];
  const now = new Date();
  for (let back = DASH_PACE_DAYS - 1; back >= 0; back -= 1) {
    const at = new Date(now);
    at.setDate(now.getDate() - back);
    at.setHours(0, 0, 0, 0);
    days.push({ at, words: 0 });
  }
  const first = days[0].at.getTime();
  for (const entry of entries) {
    const at = new Date(entry.created_at);
    if (Number.isNaN(at.getTime()) || at.getTime() < first) continue;
    const index = Math.floor((at.setHours(0, 0, 0, 0) - first) / 86400000);
    if (index < 0 || index >= days.length) continue;
    days[index].words += entry.word_count ?? wordCount(entry.content);
  }
  const total = days.reduce((sum, day) => sum + day.words, 0);
  if (!total) {
    return dashEmpty(body, "No words yet this fortnight. Anything you write today shows up here.", { label: "ph:plus New note", run: "capture" });
  }
  const peak = Math.max(...days.map((day) => day.words), 1);

  const headline = document.createElement("p");
  headline.className = "dash-pace-total";
  const strong = document.createElement("strong");
  strong.textContent = total.toLocaleString();
  headline.append(strong, ` words in ${DASH_PACE_DAYS} days · ${Math.round(total / DASH_PACE_DAYS).toLocaleString()} a day`);
  body.appendChild(headline);

  const chart = document.createElement("div");
  chart.className = "dash-pace-chart";
  chart.setAttribute("role", "img");
  chart.setAttribute(
    "aria-label",
    `Words written each day: ${days.map((d) => `${d.at.toLocaleDateString(undefined, { weekday: "short" })} ${d.words}`).join(", ")}`
  );
  for (const day of days) {
    const column = document.createElement("div");
    column.className = "dash-pace-bar";
    //: A custom property rather than an inline `style` attribute, which this
    //: app's CSP refuses: the same rule the Loose ends meter follows.
    column.style.setProperty("--dash-pace-height", `${Math.round((day.words / peak) * 100)}%`);
    column.title = `${day.at.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })}: ${day.words.toLocaleString()} word${day.words === 1 ? "" : "s"}`;
    //: Today is marked, so the row reads as ending *now* rather than as an
    //: undated fortnight.
    if (day.at.toDateString() === new Date().toDateString()) column.classList.add("is-today");
    chart.appendChild(column);
  }
  body.appendChild(chart);

  const caption = document.createElement("p");
  caption.className = "muted dash-pace-caption";
  const best = days.reduce((a, b) => (b.words > a.words ? b : a));
  caption.textContent = `Best day: ${best.at.toLocaleDateString(undefined, { weekday: "long" })}, ${best.words.toLocaleString()} words`;
  body.appendChild(caption);
}

//: After the app has painted: the agent log stream, then the wheel-scroll wiring
//: (the strips built at run time, the Library sub-tabs and editor toolbars, are in
//: the DOM by then; idempotent per element, `data-wheel-x`). Then recordings a
//: killed tab left: the server finishes them at each start and meetings.js says
//: so once. Hooked here, not in agent-activity.js: that file is wrapped whole and
//: a `window.startApp =` there is a second owner of app.js's global (audit 1028 S66);
//: app.js and the files up to agent-activity.js sit under a gzip total (tests/test_static_compression.py).
const startAppBeforeRecover = window.startApp;
window.startApp = async function () {
  if (startAppBeforeRecover) await startAppBeforeRecover.apply(this, arguments);
  streamAgentLogs();
  wireHorizontalWheelScrolling();
  apiJson("/recordings/recover", { method: "POST", silent: true }).then((r) => r.length && ensureModule("meetings").then(() => noteRecoveredRecordings(r))).catch(() => {});
};
