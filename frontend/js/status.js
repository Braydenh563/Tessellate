// status.js: toasts, reminder notices, the notifications centre, undo and redo,
// the model manager, the status bar, extras, embeddings. Moved out of app.js on
// 2026-09-26 as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- toasts (Phase 5) ---------------------------------------------------------------

// --- reminders you actually notice (§36C) ------------------------------------------
//
// Reported: "reminders when they go off aren't really noticeable and need to be
// more evident, maybe through a browser or system/app notification?"
//
// The reason they were unnoticeable is simpler than it sounds: **nothing
// checked.** A reminder's only surface was a small badge on the Reminders tab
// button, painted by `updateReminderBadge`, which only ran when something
// happened to call `loadReminders()`. So unless you reloaded, or visited that
// tab, a reminder came due and the interface said nothing at all, forever.
//
// Three surfaces now, in increasing order of how much they interrupt:
//   · the tab badge, as before;
//   · a count in the document title, which is visible from another tab or a
//     taskbar without the app being focused;
//   · a system notification and a toast, once per reminder.
//
// The honest limit, stated because the alternative is implying otherwise:
// none of this fires while the app is closed. A local-first app with no
// background service cannot wake itself up, and pretending it can would be
// worse than the gap.

//: 60s, was 30. A reminder is due to the minute, so once a minute is the
//: granularity the data has; the second poll a minute bought nothing and was
//: two of the fourteen idle requests PLAN.md P1 counts against.
const REMINDER_POLL_MS = 60_000;
//: Which reminders have already been announced, so a once-a-minute poll does not
//: re-fire the same notification twice a minute. Kept in localStorage rather
//: than memory: a reload would otherwise re-announce everything overdue, which
//: is the most annoying possible version of this feature.
const ANNOUNCED_KEY = "announcedReminders";

function announcedReminders() {
  try {
    return new Set(prefs.json(ANNOUNCED_KEY, []));
  } catch {
    return new Set();
  }
}

function rememberAnnounced(ids) {
  // Bounded, and trimmed from the front: without a cap this grows forever in a
  // notebook that has been used for years.
  const kept = [...announcedReminders(), ...ids].slice(-200);
  prefs.set(ANNOUNCED_KEY, JSON.stringify(kept));
}

// --- the notifications centre (§36E) ----------------------------------------
//
// Tessellate already *produces* all of these events, a reminder comes due, a
// background task finishes, a skill run stalls, and shows each of them in its
// own way: a system notification, a toast, a status pill, a step timeline.
// Every one of those is a moment. Miss the moment and the event is gone.
//
// This is the place they persist after their moment has passed, which is the
// whole of what §36E asks for. Three things it is deliberately *not*:
//
// - **Not a second source of truth.** A fired reminder is still a row in the
//   reminders table; this records that it was announced, and the panel folds
//   in whatever is *currently* overdue from the server when it opens. So a
//   reminder that came due while the app was closed is not lost, even though
//   nothing was running to record it, which is the one case a purely
//   event-driven log cannot cover.
// - **Not persisted to the server.** These are ephemeral by nature and there
//   can be many of them; the notebook's preferences file is not a log.
// - **Not a promise that anything fires while the app is shut.** A local-first
//   app with no background service cannot do that, and §36C says so plainly
//   rather than implying otherwise.

const NOTIFICATIONS_KEY = "notifications";
const NOTIFICATIONS_READ_KEY = "notificationsReadAt";
//: Enough to answer "what did I miss?" and not enough to become a log file.
const MAX_NOTIFICATIONS = 50;

function storedNotifications() {
  try {
    const raw = prefs.json(NOTIFICATIONS_KEY, []);
    return Array.isArray(raw) ? raw : [];
  } catch {
    return []; // hand-edited or truncated storage costs the history, not the app
  }
}

// Record something worth remembering. `key` de-duplicates: the reminder poll
// runs every thirty seconds and must not add the same fired reminder twice.
//: Returns the row's id (null when nothing was recorded), so a toast's live
//: action can be tied to its row (`keepToastAction`).
function recordNotification({ kind, title, detail = "", key = "", action = null, runId = "" }) {
  if (kind !== "reminder" && notificationsMuted()) return null;
  const items = storedNotifications();
  const id = key || `${kind}:${title}:${Date.now()}`;
  if (key && items.some((n) => n.id === id)) return null;
  if (key && dismissedNotificationIds().has(id)) return null;
  //: `runId` ties a "Started:" row to its run, so the ending can replace it.
  items.push({ id, kind, title, detail, at: Date.now(), action, ...(runId ? { runId } : {}) });
  if (!prefs.set(NOTIFICATIONS_KEY, JSON.stringify(items.slice(-MAX_NOTIFICATIONS)))) {
    return null; // storage refused: the toast still shows, the row is not kept
  }
  renderNotificationBadge();
  return id;
}

//: **A run's "Started:" row becomes its ending** (INBOX 811 item 4, the
//: transparency agent's half): "Finished: Warming up the filing model, took
//: 4 s" or the failure, in the same row and place, under the history's key so
//: the finished list does not add a second row. Returns whether it settled.
function settleNotification(id, { key, kind, title, detail = "" }) {
  const items = storedNotifications();
  if (items.some((n) => n.id === key)) return true;
  const row = items.find((n) => n.id === id);
  if (!row) return false;
  Object.assign(row, { id: key, kind, title, detail, at: Date.now() });
  delete row.runId;
  if (!prefs.set(NOTIFICATIONS_KEY, JSON.stringify(items))) return false;
  renderNotificationBadge();
  if (!$("notif-panel")?.classList.contains("hidden")) openNotifications({ keepWatermark: true });
  return true;
}

//: The history's half of the same rule: a finished run whose "Started:" row
//: is still stored (the page reloaded mid-run, so the poll never saw it end)
//: is settled by its run id.
function settleStartedNotification(item, key) {
  if (storedNotifications().some((n) => n.id === key)) return true;
  const started = item.run_id && storedNotifications().find((n) => n.runId === item.run_id);
  return Boolean(started) && settleNotification(started.id, { key, ...taskEndingWords(item, item.label) });
}

//: "Finished: X, took 4 s", "Failed: X" with the reason, "Stopped: X".
function taskEndingWords(ended, label) {
  const took = ended ? jobDurationWords(ended.duration_ms) : "";
  const name = (ended && ended.label) || label;
  if (ended && ended.outcome === "failed") return { kind: "error", title: `Failed: ${name}`, detail: ended.detail || "" };
  if (ended && ended.outcome === "cancelled") return { kind: "task", title: `Stopped: ${name}`, detail: ended.detail || "" };
  return { kind: "task", title: `Finished: ${name}${took ? `, took ${took}` : ""}`, detail: (ended && ended.detail) || "" };
}

function notificationsReadAt() {
  return Number(prefs.get(NOTIFICATIONS_READ_KEY, null) || 0);
}

//: **Read state is a watermark, and "mark this one unread" is not.**
//:
//: Asked for directly: "also allow marking notifications as unread as well."
//: Opening the panel stamps `notificationsReadAt` with the current time, and
//: everything older than the stamp is read, which is the right model for
//: "I've seen the list" and cannot express "…except that one, I want to come
//: back to it." Rewinding the watermark to just before that item would mark
//: everything after it unread too.
//:
//: So a small set of ids sits alongside the watermark and overrides it. It
//: holds only the exceptions, which is a handful at most, and "mark all read"
//: empties it: that action means the same thing either way.
const NOTIFICATIONS_UNREAD_KEY = "notificationsForcedUnread";

function forcedUnreadIds() {
  try {
    const raw = prefs.json(NOTIFICATIONS_UNREAD_KEY, []);
    return new Set(Array.isArray(raw) ? raw : []);
  } catch {
    return new Set(); // a corrupt override list costs the flags, not the panel
  }
}

function setForcedUnreadIds(ids) {
  try {
    //: Pruned to what is still in the history: `MAX_NOTIFICATIONS` drops old
    //: rows, and an override for a row nobody can see any more would sit in
    //: storage forever keeping the badge count wrong.
    const live = new Set(storedNotifications().map((item) => item.id));
    const kept = [...ids].filter((id) => live.has(id));
    prefs.set(NOTIFICATIONS_UNREAD_KEY, JSON.stringify(kept));
  } catch {
    /* private mode: the flag just will not be remembered */
  }
}

//: **Marking one row read must not mark the rest read.** Reported: "when I
//: tick mark as complete on a single notification it does that for all of
//: them." The old code moved the *watermark* up to that row's timestamp,
//: and the watermark is "everything older than this is read", so ticking
//: the newest row silently read every row beneath it. A second override set,
//: the mirror of `forcedUnreadIds`, holds rows read *ahead* of the watermark;
//: the watermark itself only ever moves on "mark all" / opening the panel.
const NOTIFICATIONS_READ_IDS_KEY = "notificationsForcedRead";

function forcedReadIds() {
  try {
    const raw = prefs.json(NOTIFICATIONS_READ_IDS_KEY, []);
    return new Set(Array.isArray(raw) ? raw : []);
  } catch {
    return new Set();
  }
}

function setForcedReadIds(ids) {
  try {
    const known = new Set(storedNotifications().map((n) => n.id));
    prefs.set(NOTIFICATIONS_READ_IDS_KEY, JSON.stringify([...ids].filter((id) => known.has(id))));
  } catch {
    // Storage refused: the flag is lost, the panel is not.
  }
}

function isNotificationUnread(item, readAt = notificationsReadAt(), forced = forcedUnreadIds(), read = forcedReadIds()) {
  if (forced.has(item.id)) return true;
  if (read.has(item.id)) return false;
  return item.at > readAt;
}

//: **One row can be removed** (INBOX 508, the owner: "I cant delete
//: individual notifications"). Only Clear all existed. A keyed row (an
//: overdue reminder, `reminder:<id>@<due time>`) is folded back in by every open of
//: the panel while it stays overdue, so its key is remembered as dismissed,
//: or the row would come back the next time the bell is pressed. Capped:
//: keys are per reminder, a few hundred is years of them.
const NOTIFICATIONS_DISMISSED_KEY = "notificationsDismissed";

//: **A reminder's row is keyed by its due time too**, so a reminder that was
//: dismissed, snoozed and overdue again is a new row and comes back to the
//: bell (a dismissal answers "this time it was due", not "never again").
function reminderNoticeKey(reminder) {
  return `reminder:${reminder.id}@${reminder.due_at || ""}`;
}

function dismissedNotificationIds() {
  try {
    const raw = prefs.json(NOTIFICATIONS_DISMISSED_KEY, []);
    return new Set(Array.isArray(raw) ? raw : []);
  } catch {
    return new Set();
  }
}

function unreadNotifications() {
  const since = notificationsReadAt();
  const forced = forcedUnreadIds();
  return storedNotifications().filter((n) => isNotificationUnread(n, since, forced));
}

function renderNotificationBadge() {
  const button = $("notif-btn");
  if (!button) return;
  const count = unreadNotifications().length;
  button.dataset.count = count > 9 ? "9+" : String(count || "");
  button.classList.toggle("has-unread", count > 0);
  const muted = notificationsMuted();
  // The bell itself says whether anything but a reminder will actually get
  // through: asked for directly, so muting isn't a setting you have to
  // remember you turned on three screens away.
  setLabel(button, muted ? "ph:bell-slash" : "ph:bell");
  button.setAttribute(
    "aria-label",
    (count ? `Notifications: ${count} unread` : "Notifications") +
      (muted ? " (muted except reminders)" : "")
  );
}

// The mute toggle's own state, kept in sync wherever it's shown: the bell
// icon above, and this button inside the panel it opens.
function renderNotifMuteToggle() {
  const button = $("notif-mute-toggle");
  if (!button) return;
  const muted = notificationsMuted();
  setLabel(button, muted ? "ph:bell-slash" : "ph:bell");
  // button.textContent = muted ? "Bell Unmute" : "bell slash Mute";
  button.title = muted
    ? "Stop muting: everything will notify again"
    : "Mute notifications except reminders";
  button.setAttribute("aria-pressed", String(muted));
  //: Icon-only since the head lost its second row, so the tooltip is no
  //: longer backed by a visible word, the accessible name has to carry it.
  button.setAttribute("aria-label", button.title);
  button.classList.toggle("active", muted);
}

async function toggleNotificationMute() {
  const next = !notificationsMuted();
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ notifications_muted_except_reminders: next }),
  });
  renderNotifMuteToggle();
  renderNotificationBadge();
}

$("notif-activity-mode")?.addEventListener("change", async (event) => {
  const value = event.currentTarget.value === "centre" ? "centre" : "toasts";
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ agent_activity_notices: value }),
    });
  } catch (error) {
    toast(error.message || "Couldn't save that.", true);
  }
  renderAgentActivityMode();
});

//: Which icon a kind gets. Colour alone is never the signal (DESIGN.md), and
//: these read as a list of *kinds* rather than a list of times.
const NOTIFICATION_ICONS = {
  reminder: "ph:alarm",
  task: "ph:gear",
  run: "ph:strategy",
  error: "ph:warning",
  export: "ph:download-simple",
  assist: "ph:sparkle",
  undo: "ph:arrow-counter-clockwise",
  done: "ph:check-circle",
  info: "•",
};

//: **Every toast with an action is kept in the bell, with that action**
//: (INBOX 585, the owner: "all notifiactions that contain links or buttons
//: need to show and be accessible in the notifications panel"). A toast's
//: button lived for eight seconds and was gone.
//:
//: Two halves, because a closure cannot go into localStorage. The row stores
//: plain data: the label, and `go`, a target the app can find again by id
//: after a reload (`runNotificationGo`). This session also keeps the toast's
//: own closure (`noticeLive`), so the row does exactly what the toast did.
//: An action with no `go` (an Undo, an offer, a restart) is one-shot: pressed
//: once, from the toast or the row, it reads "Done"; after a reload it reads
//: "Expired". An Undo is valid only while it can still be undone: while its
//: action is on the app's own stack when it has one (Ctrl+Z or the toast may
//: have taken it already), otherwise for `NOTICE_UNDO_MS`.
const noticeLive = new Map();
const NOTICE_UNDO_MS = 5 * 60 * 1000;

function keepToastAction(message, label, run, { go = null, record = true, kind = "" } = {}) {
  const once = !go;
  const undo = once && /\b(undo|put it back)\b/i.test(label);
  if (!record) return () => run();
  const id = recordNotification({
    kind: kind || (undo ? "undo" : "done"),
    title: message,
    action: { label, ...(go || {}), ...(once ? { once: true } : {}) },
  });
  //: The app's stack entry this Undo stands for: callers push it just before
  //: the toast (`pushUndo` then `toastAction`), so it is the top one, now.
  const top = undoStack[undoStack.length - 1];
  const stacked = undo && top && Date.now() - top.at < 2000 ? top : null;
  const live = { run, once, used: false, until: undo && !stacked ? Date.now() + NOTICE_UNDO_MS : 0, stacked };
  if (id) noticeLive.set(id, live);
  return async () => {
    live.used = once;
    await run();
  };
}

function closeNotifications() {
  const panel = $("notif-panel");
  if (panel.classList.contains("hidden")) return;
  panel.classList.add("hidden");
  // Closing the panel is reading it: everything shown is now old news,
  // except rows deliberately kept unread (the override set survives).
  prefs.set(NOTIFICATIONS_READ_KEY, String(Date.now()));
  renderNotificationBadge();
}

// Asked when a reminder is SET, not on first load. A permission prompt with no
// context is refused by default, and a refusal is close to permanent, the
// browser will not ask again, and most people never find the site settings.
//: A refused permission says so once, in the reminders list and in Settings,
//: rather than every due reminder quietly falling back to a toast.
function syncNotifBlocked() {
  const blocked = "Notification" in window && Notification.permission === "denied";
  for (const line of document.querySelectorAll(".notif-blocked")) line.classList.toggle("hidden", !blocked);
}

function askNotificationPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission().then(syncNotifBlocked, syncNotifBlocked);
  }
}

// A reminder's chime: a third channel beside the toast and the OS
// notification ("half the time when reminders go off I don't actually
// notice"), audible in a background tab, needing no permission. Made just
// after the first gesture, when the browser is idle (the performance pass,
// 2026-10-03: `new AudioContext()` cost 44 to 56 ms inside the unlock click);
// every gesture resumes a suspended context, which is WebKit's unlock, and
// the listeners leave once it runs.
const reminderAudio = { ctx: null, building: false };
function primeReminderAudio() {
  if (reminderAudio.ctx) {
    if (reminderAudio.ctx.state === "running") {
      document.removeEventListener("pointerdown", primeReminderAudio);
      document.removeEventListener("keydown", primeReminderAudio);
    } else {
      reminderAudio.ctx.resume().catch(() => {});
    }
    return;
  }
  if (reminderAudio.building) return;
  reminderAudio.building = true;
  const build = () => {
    try {
      reminderAudio.ctx = new (window.AudioContext || window.webkitAudioContext)();
    } catch {
      // No Web Audio support, reminders still show as a toast/notification.
    }
  };
  if (window.requestIdleCallback) window.requestIdleCallback(build, { timeout: 1500 });
  else setTimeout(build, 300);
}
document.addEventListener("pointerdown", primeReminderAudio, { passive: true });
document.addEventListener("keydown", primeReminderAudio, { passive: true });

function playReminderChime() {
  if (!reminderAudio.ctx) return;
  reminderAudio.ctx.resume().catch(() => {});
  const now = reminderAudio.ctx.currentTime;
  // Two short notes, rising, reads as "an alert" rather than a UI click,
  // without being long or harsh enough to be reached for on a repeat.
  for (const [i, freq] of [523.25, 659.25].entries()) {
    const osc = reminderAudio.ctx.createOscillator();
    const gain = reminderAudio.ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    const start = now + i * 0.14;
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(0.18, start + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, start + 0.32);
    osc.connect(gain).connect(reminderAudio.ctx.destination);
    osc.start(start);
    osc.stop(start + 0.34);
  }
}

//: How long a system notification stays up before this app closes it itself.
//: Reported as notifications that "never auto close and stay open until the
//: user closes them", which is exactly what a `Notification` does when
//: nobody calls `close()` on it: the banner's own fade is the *shell's*
//: behaviour, and the notification object outlives it, sitting in the OS
//: notification centre (and, in the desktop WebView, sometimes on screen)
//: until dismissed by hand. The web platform has no `timeout` option, so the
//: only way to auto-close one is to close it.
//:
//: Longer than a toast's 5.5s because a system notification is for the case
//: where the app is not the window you are looking at.
const NOTIFICATION_AUTOCLOSE_MS = 12000;

function notify(title, body) {
  if ("Notification" in window && Notification.permission === "granted") {
    try {
      const shown = new Notification(title, {
        body,
        icon: "/favicon.svg",
        tag: "memorymap",
      });
      setTimeout(() => {
        try {
          shown.close();
        } catch {
          // A notification the OS already disposed of. Closing twice is not
          // an error worth a line in the console.
        }
      }, NOTIFICATION_AUTOCLOSE_MS);
      return true;
    } catch {
      // Some embedded shells expose the constructor and then throw. Falling
      // through to the toast is the point of returning a boolean.
    }
  }
  return false;
}

// The count in the title bar, the one surface that works while the app is in
// a background tab, which is where it usually is when a reminder comes due.
const BASE_TITLE = "Tessellate";
//: `count` is the number before it; `view` is the view and the open thing
//: (router.js, WORLD_CLASS_PLAN 22.1 item 1): "Half marathon, week 4 · Notes",
//: before the app's name, after the count.
const pageTitle = { count: 0, view: "" };

function paintTitle() {
  const base = pageTitle.view ? `${pageTitle.view} · ${BASE_TITLE}` : BASE_TITLE;
  document.title = pageTitle.count > 0 ? `(${pageTitle.count}) ${base}` : base;
}

function setTitleCount(count) {
  pageTitle.count = count;
  paintTitle();
}

function setTitleView(view) {
  pageTitle.view = String(view || "").trim();
  paintTitle();
}

//: **On time, not up to a minute late** (TIMELINE_PLAN 11 row 5): one
//: timeout set to the soonest open reminder's due time, re-set by every
//: check and every list load, so a reminder fires within a second of its
//: minute. The minute poll stays as the backstop: a hidden tab's timeout is
//: throttled, and a reminder made on another device is not in this list.
//: A one-shot timeout, not a second interval: it wakes the page once per
//: due reminder and never at rest.
const reminderDueTimer = { id: 0 };
function armReminderTimer(list) {
  clearTimeout(reminderDueTimer.id);
  const now = Date.now();
  //: An early alert is a time of its own ("1 day before").
  const times = (list || []).filter((r) => !r.done).flatMap((r) => {
    const due = new Date(r.due_at).getTime();
    return r.alert_minutes ? [due, due - r.alert_minutes * 60000] : [due];
  });
  const next = Math.min(...times.filter((t) => t > now));
  if (!Number.isFinite(next)) return;
  //: Past the browser's 24.8-day ceiling a timeout fires at once; the poll
  //: re-arms long before such a reminder comes due.
  if (next - now > 2 ** 31 - 1) return;
  reminderDueTimer.id = setTimeout(checkDueReminders, next - now + 250);
}

async function checkDueReminders() {
  // Before the unlock there is no token, and asking anyway is a guaranteed 401
  // on every load: visible in the browser's network log, and in the server's
  // own log, where it looks like an auth failure worth investigating.
  if (!authToken()) return;
  syncNotifBlocked();
  //: Open ones only. The route orders by `due_at` ascending with ticked-off
  //: rows included by default, so this poll's one page was the *oldest*
  //: reminders, done or not: a notebook whose oldest two hundred were done
  //: never heard about the one due now. Without the done rows the page is
  //: the soonest open reminders, which is exactly what "is anything due"
  //: asks, and it is smaller.
  const all = await apiJson("/reminders?include_done=false", { silent: true }).catch(() => null);
  if (!all) return; // server asleep or locked, say nothing rather than guess
  const now = Date.now();
  const due = all.filter((r) => !r.done && new Date(r.due_at).getTime() <= now);
  armReminderTimer(all);
  updateReminderBadge(all);
  setTitleCount(due.length);

  const already = announcedReminders();
  //: An early alert (TIMELINE_PLAN 11 row 8) is announced once, under its
  //: own key, with how long is left; the due time is announced as before.
  const early = all
    .filter((r) => {
      const at = new Date(r.due_at).getTime();
      return !r.done && r.alert_minutes && at > now && at - r.alert_minutes * 60000 <= now && !already.has(`e${r.id}`);
    })
    .map((r) => ({ ...r, id: `e${r.id}`, early: true, text: `${r.text}, ${relativeWhen(r.due_at)}` }));
  const fresh = [...due.filter((r) => !already.has(r.id)), ...early];
  if (!fresh.length) return;
  rememberAnnounced(fresh.map((r) => r.id));
  playReminderChime();
  //: The companion holds up a small bell (avatars.js).
  if (typeof nameMarkBuddyCue === "function") nameMarkBuddyCue("bell");

  // Into the centre as well as onto the screen (§36E). A toast and a system
  // notification are both moments; this is the record that outlives them, and
  // it is the difference between "I think something was due" and knowing what.
  for (const reminder of fresh) {
    recordNotification({
      kind: "reminder",
      title: reminder.text,
      detail: `${reminder.early ? "Coming up" : "Came due"}${reminder.target_title ? `, about ${toastName(reminder.target_title)}` : ""}`,
      key: reminderNoticeKey(reminder),
      action: { tab: "reminders" },
    });
  }

  //: The system notification and its toast (TIMELINE_PLAN 11 row 4):
  //: reminder-notify.js, lazy, so a hidden tab's notification goes through
  //: the service worker with Done and Snooze on it.
  lazyScript("/js/reminder-notify.js").then((ok) => ok && announceReminders(fresh));
  loadReminders().catch(() => {});
}

//: **Once per page, however many unlocks** (audit 2026-10-05, FE-08). Every
//: unlock runs `startApp()` again, and so does any 401 that routes through
//: the lock screen, so this added another one-minute poll and two more
//: listeners each time: after four lock and unlock cycles an idle minute
//: asked `/reminders` five times. The first call wires everything; a later
//: one only checks now, which is what an unlock wants.
//: The status bar's Other devices panel (INBOX 896) from the shortcut, the
//: palette and a notice's Review: lan-watch.js draws it.
function openLanPanel() {
  lazyScript("/js/lan-watch.js").then((ok) => {
    if (ok && typeof lanOpenPanel === "function") lanOpenPanel();
  });
}

let reminderWatchStarted = false;
function startReminderWatch() {
  checkDueReminders();
  //: Other devices asking to sign in, and a network nobody allowed (INBOX
  //: 867): lan-watch.js, lazy, starts itself once; it also paints the status
  //: bar's Other devices icon (INBOX 896), and stops only on another device.
  lazyScript("/js/lan-watch.js");
  //: The Local chip (row 1641) asks again at each unlock too, and rides the
  //: reminder tick below; it starts here so the boot sequence in app.js (capped
  //: by test_static_compression) carries no extra step.
  startPrivacyChip();
  if (reminderWatchStarted) return;
  reminderWatchStarted = true;
  //: One minute tick for both: the reminders, and the Local chip every
  //: fifth (PRIVACY_CHIP_MS), rather than a second interval waking the page.
  let ticks = 0;
  setInterval(() => {
    checkDueReminders();
    if (++ticks % (PRIVACY_CHIP_MS / REMINDER_POLL_MS) === 0) refreshPrivacyChip();
  }, REMINDER_POLL_MS);
  // A machine that was asleep wakes up with reminders long past due, and the
  // interval will not have run. Checking on focus catches that immediately
  // rather than up to a minute later.
  window.addEventListener("focus", () => checkDueReminders());
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) checkDueReminders();
  });
}

// Asked directly: "an option to mute notifications except for reminders".
// A reminder toast passes `exempt: true` so it still gets through; an error
// always does too: silencing a real failure would hide the thing muting is
// least meant to hide. Everything else (background jobs, agent runs, general
// activity) is what the toggle actually quiets.
function notificationsMuted() {
  return Boolean(prefsCache && prefsCache.notifications_muted_except_reminders);
}

//: **Where the AI's own activity is announced.**
//:
//: Asked for directly: *"make an option for agent activity notifications to be
//: hidden and not show up as toast notifications but somewhere else."* The
//: somewhere else already existed, the notifications centre records every one
//: of these: so this is only about whether a toast also flies past the corner
//: of the screen while you are reading something.
//:
//: Deliberately not the existing mute: that one suppresses the *record* as
//: well, so a muted app forgets what it did. This keeps the history and drops
//: the interruption, which is what was actually asked for.
function agentActivityQuiet() {
  return (prefsCache && prefsCache.agent_activity_notices) === "centre";
}

//: One call for "the AI did something worth mentioning". Always recorded,
//: shown as a toast only when the reader wants them. Every background-job and
//: run notice goes through this rather than `toast` directly: a rule that
//: only some of them followed would be a setting that half works.
function agentActivityNotice(message, { isError = false, kind = "task", detail = "", action = null, onOpen = null } = {}) {
  recordNotification({ kind: isError ? "error" : kind, title: message, detail, action });
  //: **Both switches bind here, errors included.** Reported twice: "the agent
  //: activity straight up ignores muted notifications even when on panel only"
  //: and "notifications for the background agent appeared when I had them
  //: muted??".
  //:
  //: `toast()` lets an error through whatever the mute says, and that is right
  //: for a *failure the user caused and is waiting on*, a save that did not
  //: save. It is wrong here: a background pass failing to tag a note is
  //: precisely the unattended chatter these two settings exist to quiet, and
  //: the notifications centre above has already recorded it, so nothing is
  //: lost by not flying it past the corner of the screen.
  if (agentActivityQuiet() || notificationsMuted()) return;
  //: A notice with somewhere to go carries the way there on the toast as
  //: well as on its row in the bell, so the reader who sees it fly past does
  //: not have to open the bell to act on it.
  if (onOpen) toastAction(message, "Open", onOpen, { record: false });
  else toast(message, isError);
}

//: **An answer that finished while its panel was shut** (the owner,
//: 2026-09-23: "if an AI response is started in the popup agent or the Atlas
//: guide and the user closes the panel before it finishes, post a
//: notification"). Closing either panel never stopped the run, the answer was
//: still written into a transcript nobody could see, and nothing said it had
//: arrived. Called by both panels at the end of a turn, only when that panel
//: is closed at that moment: a panel that is open is its own notice.
//:
//: The action is plain data because notifications live in localStorage: the
//: panel's name and the answer's id, which `reopenAnswerPanel` turns back
//: into "open the panel on that answer". After a reload the transcript is
//: gone and the id finds nothing, so it opens the panel and stops there.
const ANSWER_PANEL_NAMES = { agent: "Popup agent", guide: "Atlas" };

function noticeUnwatchedAnswer(panel, question, answerId, { failed = false } = {}) {
  const who = ANSWER_PANEL_NAMES[panel];
  if (!who) return;
  const action = { panel, answer: answerId || "" };
  agentActivityNotice(
    failed ? `${who} could not answer: ${agentRunTitle(question)}` : `${who} answered: ${agentRunTitle(question)}`,
    {
      isError: failed,
      detail: "Open it to read the answer.",
      action,
      onOpen: () => reopenAnswerPanel(action),
    },
  );
}

function reopenAnswerPanel({ panel, answer } = {}) {
  let list = null;
  if (panel === "agent") {
    if (cmdPaletteOverlay.classList.contains("hidden")) toggleAgentPalette();
    list = cmdPaletteResults;
  } else if (panel === "guide") {
    openHelpChat();
    list = $("help-chat-messages");
  }
  if (!list || !answer) return;
  const row = [...list.querySelectorAll("[data-answer-id]")].find((el) => el.dataset.answerId === answer);
  if (!row) return;
  //: The list's own scrollTop, never `scrollIntoView`, which walks every
  //: scrolling ancestor and moves the page under the panel (DESIGN.md's
  //: recipe for a list that says where you are). After a frame, because the
  //: guide's sheet is built by the call above and has no size until then.
  requestAnimationFrame(() => {
    list.scrollTop += row.getBoundingClientRect().top - list.getBoundingClientRect().top;
  });
}

function renderAgentActivityMode() {
  const select = $("notif-activity-mode");
  if (!select) return;
  select.value = agentActivityQuiet() ? "centre" : "toasts";
}

// Asked for directly: "allow popup notifications to be manually closable
// with an x button if the user wants them gone faster". A toast that has
// already been read is just something left to wait out otherwise, the
// timer clears when this fires, so a stray late setTimeout can't reach for
// a note the click already removed.
//: **One stack in the corner** (the owner 2026-10-11: "lots of the same
//: notifcations dont neatly stack when they appear fast in the corner").
//: Measured before: ten identical toasts in 500 ms drew six cards (a 400 ms
//: repeat guard let every other one through), each slid in on its own
//: keyframe while the others slid by `translate`, so a card arriving at the
//: corner crossed the one it pushed away for about 120 ms.
//: The rules, each held by tests/test_notification_actions.py and
//: `scratchpad/ui-sweeps/toaststack.js`:
//: - the same words of the same kind (and, with an action, the same action)
//:   within `TOAST_MERGE_MS` are one card with a count ("×3"), its timer
//:   restarted; an Undo merges only with the same Undo, never another's;
//: - the newest is nearest the corner (the bottom on a desktop, the top
//:   below 1100 where the box hangs from the header), the gap is the box's
//:   `--space-2`;
//: - positions come from the stack: measured, changed, played back by
//:   `translate` (FLIP), and an arrival rides in by the same distance the
//:   others move, on the same curve, so two cards never cross;
//: - three show; the rest fold into one "+N more" card that opens the bell,
//:   and a folded notice is written to the bell so it is not lost;
//: - reduced motion fades and never slides; interface animations off jumps.
const TOAST_MERGE_MS = 4000;
const TOAST_VISIBLE = 3;
let toastBorn = 0;

function toastAtTop(box) {
  return box.getBoundingClientRect().top < window.innerHeight / 2;
}

function toastLive(box) {
  return [...box.children]
    //: Only cards `toastMark` stamped: the server-down banner and the
    //: semantic notice stay up whatever arrives after them.
    .filter((t) => t.toastBorn && !t.classList.contains("is-leaving"))
    .sort((a, b) => (b.toastBorn || 0) - (a.toastBorn || 0));
}

//: Folds all but the newest `TOAST_VISIBLE` into one "+N more" card at the
//: far end of the stack, away from the corner.
function toastLayout(box) {
  const live = toastLive(box);
  const folded = live.slice(TOAST_VISIBLE);
  for (const t of live) t.classList.toggle("is-folded", folded.includes(t));
  for (const t of folded) {
    if (t.toastKept || t.toastFiled) continue;
    t.toastFiled = true;
    recordNotification({ kind: t.classList.contains("error") ? "error" : "done", title: t.toastText || t.textContent.trim() });
  }
  let more = box.querySelector(":scope > .toast-more");
  if (!folded.length) {
    more?.remove();
    return;
  }
  if (!more) {
    more = document.createElement("div");
    more.className = "toast toast-more";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "ghost small toast-more-open";
    open.addEventListener("click", () => $("notif-btn")?.click());
    more.append(open);
  }
  const open = more.firstElementChild;
  open.textContent = `+${folded.length} more`;
  open.title = "Open the notifications";
  open.setAttribute("aria-label", `${folded.length} more notifications. Open the notifications`);
  if (toastAtTop(box)) box.append(more);
  else box.prepend(more);
}

//: The same notice again: the card it is already on counts it and starts its
//: time again. Returns whether it merged.
function toastMerge(box, key, act = null) {
  const now = Date.now();
  const same = [...box.children].find((t) => t.toastKey === key && t.toastAct === act && !t.classList.contains("is-leaving") && now - t.toastAt < TOAST_MERGE_MS);
  if (!same) return false;
  same.toastAt = now;
  same.toastCount = (same.toastCount || 1) + 1;
  const msg = same.querySelector(":scope > .toast-msg");
  let badge = msg?.querySelector(":scope > .toast-count");
  if (msg && !badge) {
    badge = document.createElement("span");
    badge.className = "toast-count";
    msg.append(badge);
  }
  if (badge) {
    badge.textContent = `×${same.toastCount}`;
    badge.setAttribute("aria-label", `${same.toastCount} times`);
  }
  if (same.toastLife) {
    clearTimeout(same.toastTimer);
    same.toastTimer = setTimeout(() => dismissToast(same), same.toastLife);
  }
  return true;
}

//: Stamps a card for the stack: when it was born, what merges with it, how
//: long it lives.
function toastMark(note, key, { act = null, life = 0, text = "" } = {}) {
  note.toastBorn = ++toastBorn;
  note.toastKey = key;
  note.toastAct = act;
  note.toastAt = Date.now();
  note.toastLife = life;
  note.toastText = text;
}

//: Reduced motion (the system's, or Appearance's Reduce motion) keeps the
//: fades, which are the polish set's and follow Interface animations, but
//: never slides the stack (the owner 2026-10-11).
function toastReduced() {
  return Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
    || document.documentElement.dataset.motion === "reduced";
}

function toastStack(box, change) {
  if (!box) return change();
  const shown = (t) => t.getClientRects().length > 0;
  const was = new Map([...box.children].filter(shown).map((t) => [t, t.getBoundingClientRect().top]));
  const before = new Set(box.children);
  change();
  const top = toastAtTop(box);
  //: Newest nearest the corner: a card the caller appended goes first when
  //: the stack hangs from the top.
  for (const t of [...box.children]) if (!before.has(t) && top) box.prepend(t);
  toastLayout(box);
  const cs = getComputedStyle(box);
  const ms = parseFloat(cs.getPropertyValue("--ui-base")) * 1000;
  if (!ms || toastReduced()) return;
  const ease = cs.getPropertyValue("--ease-out");
  let shift = 0;
  for (const [t, at] of was) {
    if (!t.isConnected || !shown(t)) continue;
    const dy = at - t.getBoundingClientRect().top;
    if (!dy) continue;
    shift = dy;
    t.animate([{ translate: `0 ${dy}px` }, { translate: "0 0" }], { duration: ms, easing: ease });
  }
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const step = (parseFloat(cs.getPropertyValue("--space-4")) || 1) * rem * (top ? -1 : 1);
  for (const t of box.children) {
    if (was.has(t) || !shown(t) || t.classList.contains("toast-more")) continue;
    t.animate([{ translate: `0 ${shift || step}px` }, { translate: "0 0" }], { duration: ms, easing: ease });
  }
}

//: **A toast leaves in place** (INBOX 399 (4)): it fades and shrinks on the
//: exit curve (`.toast.is-leaving`, 01-forms-settings.css) without moving,
//: so it never crosses a neighbour, and the stack then closes the gap.
//: Removed on `animationend`, with a timer behind it for the case where no
//: animation runs at all.
function dismissToast(note) {
  if (!note.isConnected || note.classList.contains("is-leaving")) return;
  note.classList.add("is-leaving");
  const done = () => note.isConnected && toastStack(note.parentElement, () => note.remove());
  note.addEventListener("animationend", done, { once: true });
  setTimeout(done, 400);
}

function toastCloseButton(note, timer) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "toast-close";
  setLabel(button, "ph:x");
  button.title = "Dismiss";
  button.setAttribute("aria-label", "Dismiss this notification");
  button.addEventListener("click", () => {
    clearTimeout(timer);
    dismissToast(note);
  });
  return button;
}

//: The last toast's text and when it landed, so a click that somehow fires
//: two handlers for one gesture (CM6's own event dispatch does not always
//: agree with a plain DOM `stopPropagation` about which handler runs) shows
//: one notice, not two stacked identical ones. Reported on a wiki-link
//: click: `[[Act I, Scene I]]` toasted the same "not found" message twice.
//: A real repeat within the window is rare enough (nobody clicks a broken
//: link twice inside 400ms on purpose) that this costs nothing anyone would
//: notice, and it is the whole message plus severity that must match, not
//: just the timing, so two different toasts arriving close together both
//: still show.
//: Where a support bundle goes; the same string as `tessellate.SUPPORT_EMAIL`
//: (tests/test_support_email.py keeps them equal).
const SUPPORT_EMAIL = "brayden.hoyle@outlook.com";


//: A toast steps aside for the focused control it covers (WCAG 2.4.11,
//: measured at 200% and 400% zoom: a lasting "3 reminders are due" hid the
//: Tab stop under it on six tabs). Fades and lets clicks through until focus
//: moves off it; focus inside the toast itself never counts.
document.addEventListener("focusin", (e) => {
  const box = $("toast-box");
  if (!box?.children.length || box.contains(e.target)) return box?.classList.remove("is-yielding");
  const r = e.target.getBoundingClientRect();
  box.classList.toggle("is-yielding", [...box.children].some((el) => {
    const b = el.getBoundingClientRect();
    return b.left < r.right && b.right > r.left && b.top < r.bottom && b.bottom > r.top;
  }));
});

//: **Where a toast goes** (INBOX 470): inside the open modal dialog while
//: there is one, because a modal makes everything outside it inert and draws
//: over it, so a page toast's Undo could be neither seen nor pressed; the
//: page's box otherwise. The host is fixed to the window like the box.
function toastHost() {
  const dialog = document.querySelector("dialog:modal");
  if (!dialog) return $("toast-box");
  let host = dialog.querySelector(":scope > .toast-host");
  if (!host) {
    host = document.createElement("div");
    host.className = "toast-host";
    host.setAttribute("aria-live", "polite");
    dialog.appendChild(host);
  }
  return host;
}

// What a person is told when a request fails (INBOX 472, "official, not a
// demo"). Every error toast in the app prints `error.message`, and that
// message was whatever the server's `detail` held: FastAPI's validation
// answer is a list, so a toast read `[{"type":"missing","loc":["body",...`
// (and `[object Object]` where a caller concatenated it); a server fault was
// the bare word "Internal error"; a missing route was "Not Found". A detail
// the app's own code wrote as a sentence ("Entry not found") is kept exactly,
// because a few callers read it. Only the shapes no person should see are
// replaced; `api()` still logs the raw text to Settings > Logs, where
// someone diagnosing it wants it.
//
// `fallback` is for a caller that knows what it was doing ("Upload failed.")
// and would rather say that than a generic line when the server gave nothing
// a person can read.
//
// It lives here, not in app.js: app.js is at its gzip cap
// (tests/test_static_compression.py) and this is only called at run time.
const GENERIC_HTTP_DETAIL = /^(not found|method not allowed|internal error|internal server error|bad request|unprocessable entity|forbidden|bad gateway|service unavailable|gateway timeout)\.?$/i;
function plainHttpError(status, detail, fallback = "") {
  if (typeof detail === "string" && detail.trim() && !GENERIC_HTTP_DETAIL.test(detail.trim())) return detail;
  if (typeof detail?.message === "string" && detail.message.trim()) return detail.message;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] || {};
    const loc = Array.isArray(first.loc) ? first.loc.filter((part) => part !== "body" && part !== "query") : [];
    const field = loc.length ? String(loc[loc.length - 1]).replace(/_/g, " ") : "";
    return field ? `Check the ${field} and try again.` : "That was not accepted. Check what you entered and try again.";
  }
  if (fallback) return fallback;
  if (status === 404) return "That could not be found. It may have been deleted.";
  if (status === 400 || status === 405 || status === 422) return "That was not accepted. Try again.";
  if (status === 403) return "That is not allowed.";
  if (status >= 500) return "Something went wrong inside Tessellate. Try again; if it keeps happening, Settings > Logs has the details.";
  return "That did not work. Try again.";
}

//: One gesture that fires two handlers (CM6's dispatch and a DOM listener on
//: one click) shows one notice: the same words in the same task are dropped.
//: A repeat in a later task is a real repeat and merges with a count.
let lastToastKey = "";
//: **An error toast is for a fault; a situation the app expects is a plain one**
//: (the owner's end-to-end pass: Dictate without the voice add-on, Compress on
//: an empty chat, Add on an empty reminder all showed red and "Report this",
//: which reads as a broken app). Two ways in, one rule:
//: - a call site that knows the situation passes `"info"` (a check on what
//:   the person entered, nothing to do yet, a missing add-on): a plain toast,
//:   no "Report this", and it ignores "mute notifications" because it answers
//:   something the person just pressed;
//: - a call site that passes `true` for a failed request gets the same
//:   treatment when the server answered with a 4xx, which is a refusal by
//:   design (`api()` in app.js notes each 4xx message in `toast.refused`).
//: Only a 5xx, a network failure or an unexpected exception keeps the red
//: style and the report button. `tests/test_error_toasts.py` pins both.
//:
//: **An error explains and offers** (WORLD_CLASS_PLAN 28.1 rule 4): an error
//: toast always carries one action. A caller that knows the way forward passes
//: it, `{ action: ["Try again", fn] }`; one that does not gets Open the logs,
//: Settings, Logs, where the why is written (the message says what happened).
//: `tests/test_error_toasts.py` holds the literal faults to an action of their own.
//: **The app's voice for what it says itself** (CHAT_PLAN decision 55,
//: Brief 68 row 9): one register for a failure, "Couldn't open that
//: document.", never "Could not" beside "Couldn't", never an exclamation. The
//: table is the realiser's (`ai/realise.py` `VOICE`); tests/test_voice_tables.py
//: holds the two equal and counts the surfaces moved onto it (the Library,
//: the board and the map first, the three with the most toasts).
const VOICE = {
  failed: "Couldn't {what}.",
  failed_why: "Couldn't {what}: {why}",
};

//: **A toast names the thing** (CHAT_PLAN section 1 row 3): `“Passport
//: renewal”`, cut to a short run, so "Moved to the bin." says what moved.
//: **One shape for a date and its time** (WORLD_CLASS_PLAN: "every date and time
//: follows one setting"): the reader's locale, to the minute. The bare
//: `toLocaleString()` printed seconds on version lists, notes' hovers and run
//: logs while the Timeline and the reminders printed none, and 12 or 24 hours
//: follows the locale's own rule everywhere.
const WHEN_FORMAT = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
function whenText(value = new Date()) {
  const moment = value instanceof Date ? value : new Date(value);
  return Number.isNaN(moment.getTime()) ? "" : WHEN_FORMAT.format(moment);
}

function toastName(text, fallback = "it", limit = 48) {
  const flat = String(text || "").replace(/\s+/g, " ").trim();
  if (!flat) return fallback;
  return `“${flat.length > limit ? `${flat.slice(0, limit - 1).trimEnd()}…` : flat}”`;
}

function voiceLine(key, slots = {}) {
  const why = slots.why ? String(slots.why).trim() : "";
  const shape = VOICE[key === "failed" && why ? "failed_why" : key] || "";
  return shape.replace(/\{(\w+)\}/g, (_, name) => (name === "why" ? why : String(slots[name] ?? "")));
}

function toast(message, isError = false, { exempt = false, action = null } = {}) {
  if (isError === "info" || (isError === true && [...toast.refused].some((m) => String(message).includes(m)))) {
    isError = false;
    exempt = true;
  }
  if (!exempt && !isError && notificationsMuted()) return;
  const key = `${isError ? "1" : "0"}:${message}`;
  if (key === lastToastKey) return;
  lastToastKey = key;
  setTimeout(() => {
    if (lastToastKey === key) lastToastKey = "";
  }, 0);
  const box = toastHost();
  if (toastMerge(box, key, action?.[1] || null)) return;
  //: An error makes the companion jump (avatars.js).
  if (isError && typeof nameMarkBuddyCue === "function") nameMarkBuddyCue("startle", "error");
  const note = document.createElement("div");
  note.className = isError ? "toast error" : "toast";
  const text = document.createElement("span");
  text.className = "toast-msg";
  text.textContent = message;
  note.appendChild(text);
  //: An error toast carries the way to report it (INBOX 256): one small
  //: button that saves the support bundle and opens a mail to the owner
  //: with the message already in it. Plain toasts stay plain.
  if (isError) {
    const [label, run] = action || ["Open the logs", () => openSettingsModal("logs")];
    const act = toastActionButton(note, label, () => {
      clearTimeout(timer);
      run();
    });
    const help = document.createElement("button");
    help.type = "button";
    help.className = "ghost small toast-help";
    help.textContent = "Report this";
    help.title = `Save the support bundle and email it to ${SUPPORT_EMAIL}`;
    help.addEventListener("click", () => {
      clearTimeout(timer);
      dismissToast(note);
      emailSupportReport(message);
    });
    note.appendChild(toastActions(act, help));
  }
  const timer = setTimeout(() => dismissToast(note), isError ? 9000 : 5500);
  toastMark(note, key, { act: action?.[1] || null, life: isError ? 9000 : 5500, text: String(message) });
  note.toastTimer = timer;
  note.appendChild(toastCloseButton(note, timer));
  //: A tap on the words dismisses it, the way a phone's own banners go
  //: (below 1100 a toast comes down from the top, over the head of a list,
  //: and the small close button is not the only way to clear it). Its
  //: buttons keep their own jobs.
  note.addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    clearTimeout(timer);
    dismissToast(note);
  });
  toastStack(box, () => box.appendChild(note));
}
toast.refused = new Set();

// A toast with one action button, used for Undo (Wave J). The button
// stays until clicked or the toast times out (a bit longer than usual,
// since the user has to react to it).
//: **A toast that stays until the work it is announcing finishes.**
//:
//: Reported of OCR: *"if i close the lightbox as I am generating ocr, then it
//: stops and I have to restart it again. also ocr generation is slow and i
//: dont even know if it is working."* The second half is this function's job.
//: Every other toast in the app is a 5.5-second notice about something that
//: already happened; a job that takes thirty seconds needs the opposite, a
//: notice that persists *while* it happens and then reports what it found.
//:
//: Returns a handle rather than a node: the caller finishes the job, and
//: finishing it is one call rather than a DOM edit at each of its exits.
function toastProgress(message) {
  const box = toastHost();
  const note = document.createElement("div");
  note.className = "toast";
  const text = document.createElement("span");
  text.className = "toast-msg";
  setLabel(text, `ph:spin ${message}`);
  note.append(text);
  toastMark(note, null, { text: String(message) });
  toastStack(box, () => box.appendChild(note));
  return {
    say(next) {
      setLabel(text, `ph:spin ${next}`);
    },
    //: `done` swaps the spinner for the outcome and starts the ordinary
    //: 5.5-second life every other toast has, so a finished job does not
    //: leave a permanent line on screen.
    //: Its action is the toast recipe's button and is kept in the bell like
    //: any other (INBOX 584: a bare link here read "this file.Show it").
    done(finalMessage, { isError = false, actionLabel = null, onAction = null, go = null, record = true } = {}) {
      text.textContent = finalMessage;
      note.classList.toggle("error", Boolean(isError));
      if (actionLabel && onAction) {
        note.appendChild(toastActions(toastActionButton(note, actionLabel, keepToastAction(finalMessage, actionLabel, onAction, { go, record }))));
      }
      note.toastTimer = setTimeout(() => dismissToast(note), 5500);
      note.appendChild(toastCloseButton(note, note.toastTimer));
    },
  };
}

//: **A notification's actions are their own row** (INBOX 847: "notification
//: buttons are still in line with the x close button ... it looks weird"): the
//: message and the close button are the first row, the actions sit under the
//: message, left-aligned with its words (`.toast-actions`, 02-chat-graph.css),
//: so the close X is alone in its corner.
function toastActions(...buttons) {
  const row = document.createElement("div");
  row.className = "toast-actions";
  row.append(...buttons);
  return row;
}

//: One action on a toast (INBOX 584): a small button after the message,
//: spaced by the toast's own gap, never a bare link glued to the words.
function toastActionButton(note, label, run) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "small toast-action";
  button.textContent = label;
  button.addEventListener("click", async () => {
    clearTimeout(note.toastTimer);
    dismissToast(note);
    await run();
  });
  return button;
}

//: `opts`: `go`, where the action leads as plain data, so its row in the
//: bell still works after a reload; `record: false` for a notice that is
//: already in the bell (`keepToastAction`); `also: {label, run}`, a second
//: button beside the first (a bin notice's "Go to bin" next to its Undo,
//: INBOX 705). It is the toast's own and is not kept in the bell: its row
//: keeps the one action it always had. `ms` is how long it stays (8 s by
//: default; a clear that can be undone passes 10 s).
function toastAction(message, actionLabel, onAction, opts = {}) {
  const box = toastHost();
  const key = `a:${message}:${actionLabel}`;
  if (toastMerge(box, key, onAction)) return;
  const run = keepToastAction(message, actionLabel, onAction, opts);
  const note = document.createElement("div");
  note.className = "toast";
  const text = document.createElement("span");
  text.className = "toast-msg";
  text.textContent = message;
  // `sticky`: a notice that stays true until acted on (a damaged notebook
  // file) is not timed out; its close button is the way to put it away.
  note.toastTimer = opts.sticky ? null : setTimeout(() => dismissToast(note), opts.ms || 8000);
  const buttons = [toastActionButton(note, actionLabel, run)];
  if (opts.also) buttons.push(toastActionButton(note, opts.also.label, opts.also.run));
  note.append(text, toastActions(...buttons), toastCloseButton(note, note.toastTimer));
  toastMark(note, key, { act: onAction, life: opts.sticky ? 0 : opts.ms || 8000, text: String(message) });
  note.toastKept = true;
  toastStack(box, () => box.appendChild(note));
}

//: The notebook file's check at start (`GET /backups/integrity`, WORLD_CLASS
//: 25e) in one sentence that says what to do. Shared by the boot notice and
//: Settings, Import & export, so both say the same thing.
function integrityWords() {
  return "Your notebook file failed its check at start. Restore the newest backup in Settings, Import & export.";
}

function noteDamagedNotebook(check) {
  if (!check || check.ok !== false) return;
  toastAction(integrityWords(), "Open backups", () => openSettingsModal("data", "backup-now"), {
    go: { settings: "data", focus: "backup-now" },
    sticky: true,
  });
}

//: The second button of every "Moved to the bin." notice: the bin is the
//: Library with "Include the bin" ticked (`library-bin` in REVEAL_TARGETS), so
//: this is the same place Settings and Ctrl+K "Open the bin" lead to.
const GO_TO_BIN = { label: "Go to bin", run: () => revealFeature("library-bin") };

// --- the server-down banner (WORLD_CLASS_PLAN 22.1 item 6) ------------------
//
// Reported gap: "the server can go away. Only the log view says
// 'reconnecting'... everywhere else a stopped backend shows as buttons that
// do nothing." `api()` (app.js) already tells a real network failure (the
// backend is not there to answer) apart from every other kind of error, it
// used to just log one and rethrow; now it calls `noteServerDown` there and
// `noteServerUp` on its next success, so this file never polls a fetch of
// its own except while there is a failure to recover from.
//
// This reuses the toast recipe rather than inventing a banner: same node,
// same `.toast`/`.toast-action` classes and close button, the one thing
// different is that it never starts the usual timeout, because the message
// it carries stays true until the retry says otherwise. `noteServerDown`
// is idempotent (a second failed request while the banner is already up is
// a no-op, no stacked banners, no restarted backoff), and there is exactly
// one retry loop, cancelled and restarted from one place
// (`scheduleServerDownRetry`) so a manual Retry press and the poll it
// interrupts can never both be running at once.
let serverUnreachable = false;
let serverDownNote = null; // the persistent toast's own node, or null
let serverDownRetryTimer = null;
const SERVER_DOWN_RETRY_MIN_MS = 3000;
const SERVER_DOWN_RETRY_MAX_MS = 30000;
let serverDownRetryDelay = SERVER_DOWN_RETRY_MIN_MS;

function showServerDownBanner() {
  if (serverDownNote && serverDownNote.isConnected) return; // already up
  const box = $("toast-box");
  const note = document.createElement("div");
  note.className = "toast error server-down-toast";
  const text = document.createElement("span");
  text.className = "toast-msg";
  text.textContent = "Can't reach Tessellate. Retrying…";
  const button = document.createElement("button");
  button.className = "small toast-action";
  button.textContent = "Retry";
  button.addEventListener("click", () => retryServerNow());
  note.append(text, toastActions(button), toastCloseButton(note, null));
  toastStack(box, () => box.appendChild(note));
  serverDownNote = note;
}

function noteServerDown() {
  serverUnreachable = true;
  showServerDownBanner();
  scheduleServerDownRetry();
}

//: Cheap to call on every successful request, not just from the retry poll:
//: an ordinary request succeeding is the fastest possible sign the server is
//: back, no reason to make someone wait out the backoff for it.
function noteServerUp() {
  if (!serverUnreachable) return;
  serverUnreachable = false;
  serverDownRetryDelay = SERVER_DOWN_RETRY_MIN_MS;
  if (serverDownRetryTimer) {
    clearTimeout(serverDownRetryTimer);
    serverDownRetryTimer = null;
  }
  if (serverDownNote) {
    dismissToast(serverDownNote);
    serverDownNote = null;
  }
  flushNoteOutbox(); // notes kept on this device while it was gone
}

function scheduleServerDownRetry() {
  if (serverDownRetryTimer) return; // one loop at a time
  serverDownRetryTimer = setTimeout(async () => {
    serverDownRetryTimer = null;
    await pollServerHealth();
  }, serverDownRetryDelay);
  serverDownRetryDelay = Math.min(serverDownRetryDelay * 2, SERVER_DOWN_RETRY_MAX_MS);
}

//: `/health` takes no auth and answers before the lock screen, the same
//: reason the startup probe uses it: it is the cheapest possible "is
//: anything listening" question, and does not confuse "the server is up but
//: this endpoint needs a token" with "there is no server".
async function pollServerHealth() {
  try {
    const response = await fetch("/health", { signal: AbortSignal.timeout(4000) });
    if (response.ok) {
      noteServerUp();
      return;
    }
  } catch {
    // still down; fall through to reschedule
  }
  if (serverUnreachable) scheduleServerDownRetry();
}

function retryServerNow() {
  if (serverDownRetryTimer) {
    clearTimeout(serverDownRetryTimer);
    serverDownRetryTimer = null;
  }
  pollServerHealth();
}

// --- global undo/redo (status bar) ------------------------------------------------
//
// The app already had per-action undo scattered across it, a toast's Undo
// button on note/reminder delete, the whiteboard's own local history, a
// per-tool-call "put this back" in the agent panel. None of those help once
// the toast has timed out, or for the actions that never got one (linking
// two notes, editing a note's body, attaching an image). This is the one
// mechanism that catches all of it: any mutation that can name its own
// inverse calls `pushUndo(label, undo, redo)`, and the status bar's Undo/Redo
// buttons (plus Ctrl+Z/Ctrl+Shift+Z) work the two stacks below. Session-only
// by design: like the rest of this app's undo, it does not survive a reload,
// which is the same lifetime a browser's own Ctrl+Z already has.
const undoStack = [];
const redoStack = [];
const UNDO_STACK_LIMIT = 50;

function pushUndo(label, undo, redo) {
  //: `at`: a toast's Undo finds the entry it stands for (`keepToastAction`).
  const action = { label, undo, redo, at: Date.now() };
  undoStack.push(action);
  if (undoStack.length > UNDO_STACK_LIMIT) undoStack.shift();
  // A fresh action invalidates whatever was available to redo, the same
  // rule every text editor's undo stack already follows.
  redoStack.length = 0;
  renderUndoBar();
  return action;
}

//: **An insight line's two verdicts** (CHAT_PLAN decision 60): Confirm writes
//: it as a fact the person vouched for ("Golf is a hobby of yours (confirmed
//: by you, 10 October)"), said that way from the next answer on; Not right
//: keeps it, and every near-variant of it, from being shown again. **One
//: compact pair on the sentence's own row** (INBOX 782, the owner: "redesign
//: the confirm and not right buttons ... and any other similar instances"): a
//: check and a cross with their words, quiet at rest, right-aligned, drawn by
//: `insightLine` for Chat and Tidy's Patterns and by `INSIGHT_VERDICT_ITEMS`
//: for the dashboard's ⋯. `onDone(verdict, result)` lets the surface replace
//: the line; a confirmed insight is drawn with no pair.
const INSIGHT_VERDICT_ITEMS = [
  { verdict: "confirm", label: "ph:check Confirm", title: "This is right: say it as a fact from now on" },
  { verdict: "dismiss", label: "ph:x Not right", title: "Not right: never show this or anything like it again" },
];

function insightSend(insight, verdict) {
  return apiJson(`/insights/${verdict}`, { method: "POST", body: JSON.stringify(insight) });
}

//: `send` is where the verdict goes: an insight's own route by default; a
//: cited line's peek (B31, B32) sends it to `/learned/verdict` instead.
function insightVerdicts(insight, onDone, send = insightSend) {
  const group = document.createElement("span");
  group.className = "insight-verdicts";
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "Is this right?");
  for (const item of INSIGHT_VERDICT_ITEMS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `insight-verdict is-${item.verdict}`;
    if (item.title) button.title = item.title;
    setLabel(button, item.label);
    button.addEventListener("click", () =>
      send(insight, item.verdict)
        .then((result) => onDone?.(item.verdict === "confirm" ? "confirmed" : "dismissed", result))
        .catch((error) => toast(error.message, true))
    );
    group.appendChild(button);
  }
  return group;
}

//: One insight sentence with its pair on the same row: the words take the
//: room, the pair sits at the end and wraps under them on a narrow screen.
function insightLine(insight, text, onDone, extraClass = "", send = insightSend) {
  const line = document.createElement("p");
  line.className = `insight-line ${extraClass}`.trim();
  const words = document.createElement("span");
  words.className = "insight-text";
  words.textContent = text;
  line.append(words, insightVerdicts(insight, (verdict, result) => onDone?.(line, verdict, result), send));
  return line;
}

//: **Rule 1.8's one shape** (WORLD_CLASS 1.8) for an act that reached the
//: server: an entry on the undo stack (the bar, Ctrl+Z, the history menu) and
//: a toast whose Undo is that same entry, taken off the stack when pressed so
//: Ctrl+Z cannot run it a second time. `tests/test_undo_contract.py` holds
//: every other function named for an undo to this file's contract.
function offerUndo(label, message, undo, redo, opts = {}) {
  const action = pushUndo(label, undo, redo);
  toastAction(
    message,
    "Undo",
    async () => {
      settleUndoFromToast(action);
      await Promise.resolve()
        .then(undo)
        .catch((error) => toast(error.message, true));
    },
    opts
  );
  return action;
}

// A few call sites also offer an immediate toast "Undo" button alongside the
// global stack (Wave J's pattern, from before this stack existed). If that
// button is used, the action has to come off the undo stack, otherwise a
// later Ctrl+Z would redo the exact same restore, since the closure runs
// fine either way and nothing stops it firing twice.
function settleUndoFromToast(action) {
  const idx = undoStack.indexOf(action);
  if (idx !== -1) undoStack.splice(idx, 1);
  action.undoneAt = Date.now();
  redoStack.push(action);
  renderUndoBar();
}

// A `PUT /entries/{id}` before/after snapshot: the shared inverse for every
// kind of note-content edit (a manual text correction, an image attached or
// removed from the body, a tag/category change from the edit form), since
// all of them are just this one request with a different body.
function pushEntryPutUndo(entryId, label, beforeBody, afterBody) {
  pushUndo(
    label,
    async () => {
      await api(`/entries/${entryId}`, { method: "PUT", body: JSON.stringify(beforeBody) });
      await refreshEntries([entryId]);
    },
    async () => {
      await api(`/entries/${entryId}`, { method: "PUT", body: JSON.stringify(afterBody) });
      await refreshEntries([entryId]);
    }
  );
}

//: **Whose stack a press belongs to.** The board keeps its own history
//: (moves, resizes, deletes on the canvas), which the app's stack knows
//: nothing about, so while a board is open every door to undo has to lead
//: there: the status bar's two buttons, the Ctrl+Z chord, and the command
//: palette alike. Asked for directly: "make sure redo is handled too. the
//: undo and redo buttons in the bottom bar should work across the whole
//: application". Deciding it here rather than at each door is what stops the
//: three drifting: the buttons used to drive the app's stack while the chord
//: drove both.
//: **An open board, not the boards list**: the list's own actions (rename,
//: delete a board) are the app's, and went to an empty board history.
function boardHistoryActive() {
  const board = document.getElementById("library-view-whiteboard");
  const canvas = document.getElementById("wb-canvas-view");
  //: Showing, not merely un-hidden (INBOX 898, found by the live check): the
  //: board's view keeps no `hidden` class when another main tab covers it, so
  //: Ctrl+Z on Notes walked the last board's history and the app's own steps
  //: could not be reached.
  return Boolean(board && !board.classList.contains("hidden") && canvas && !canvas.classList.contains("hidden") && window.wbUndo && board.getClientRects().length);
}

//: **Which history a press walks** (the owner, 2026-10-05: "local undos and
//: redos ... for specific documents, whiteboards, mindmaps"). An open board or
//: map: its own (kept per board for the session). An open document: its own
//: editor history (kept per document for the session, `docResetDocument`).
//: Anywhere else: the app's stack below, for notes, tags, categories, links,
//: reminders and the rest. Inside a text field Ctrl+Z is always the field's.
//: `dir` is "redo" for the redo door: on a document the two can differ.
function surfaceHistory(dir = "undo") {
  if (boardHistoryActive()) {
    return { where: "board", undo: () => window.wbUndo(), redo: () => window.wbRedo?.(), canUndo: window.wbCanUndo, canRedo: window.wbCanRedo };
  }
  const docs = document.getElementById("tab-documents");
  if (docs && !docs.classList.contains("hidden") && typeof currentDoc !== "undefined" && currentDoc && window.docCanUndo && !appStackIsNewer(dir)) {
    return { where: "document", undo: () => window.docUndo(), redo: () => window.docRedo(), canUndo: window.docCanUndo, canRedo: window.docCanRedo };
  }
  return null;
}

//: **One timeline on an open document** (DOCUMENTS 24 row 1). A document's
//: own acts (rename, archive, a version restored, a note unlinked) reach the
//: server and sit on the app's stack; its typing sits in the editor's history.
//: Ctrl+Z walks whichever of the two holds the newer step, so a rename after a
//: paragraph undoes first and the paragraph next, the order they were made.
//: Before this the document's history took every press while one was open,
//: and an act on the stack could only be undone from its toast.
function appStackIsNewer(dir) {
  if (dir === "redo") {
    const top = redoStack[redoStack.length - 1];
    return Boolean(top) && (top.undoneAt || 0) >= (window.docRedoAt?.() || 0);
  }
  const top = undoStack[undoStack.length - 1];
  return Boolean(top) && top.at >= (window.docUndoAt?.() || 0);
}

async function performUndo() {
  const surface = surfaceHistory();
  if (surface) {
    await surface.undo();
    renderUndoBar();
    return;
  }
  const action = undoStack.pop();
  if (!action) return;
  try {
    await action.undo();
    action.undoneAt = Date.now();
    redoStack.push(action);
    toast(`Undone: ${action.label}`);
  } catch (error) {
    // Nothing changed: put it back rather than silently dropping it off
    // the stack, so a transient network error doesn't cost the undo itself.
    undoStack.push(action);
    toast(error.message || "Couldn't undo that.", true);
  }
  renderUndoBar();
}

async function performRedo() {
  const surface = surfaceHistory("redo");
  if (surface) {
    await surface.redo();
    renderUndoBar();
    return;
  }
  const action = redoStack.pop();
  if (!action) return;
  try {
    await action.redo();
    undoStack.push(action);
    toast(`Redone: ${action.label}`);
  } catch (error) {
    redoStack.push(action);
    toast(error.message || "Couldn't redo that.", true);
  }
  renderUndoBar();
}

//: The pair says which history it walks, so it is repainted when that
//: changes (a tab, a board, a document, a keystroke): once a frame at most.
let undoBarFrame = 0;
function scheduleUndoBar() {
  if (undoBarFrame) return;
  undoBarFrame = requestAnimationFrame(() => {
    undoBarFrame = 0;
    renderUndoBar();
  });
}

function renderUndoBar() {
  const undoBtn = $("status-undo");
  const redoBtn = $("status-redo");
  if (!undoBtn || !redoBtn) return;
  //: A board's own stack has no labels to name in the tooltip (its entries
  //: are "move this shape back", not a sentence), so the pair falls back to
  //: the plain verbs while one is open, and takes its enabled state from the
  //: board's counts: a button that is lit when there is nothing behind it is
  //: the thing that makes people stop trusting it. Each button asks for its
  //: own history, since on a document the newer step decides (`appStackIsNewer`).
  const surface = surfaceHistory();
  paintUndoDoor(undoBtn, "undo", surface, undoStack);
  paintUndoDoor(redoBtn, "redo", surfaceHistory("redo"), redoStack);
}

function paintUndoDoor(button, verb, surface, stack) {
  const redo = verb === "redo";
  const Verb = redo ? "Redo" : "Undo";
  const icon = redo ? "ph:arrow-u-up-right" : "ph:arrow-u-up-left";
  if (surface) {
    const can = redo ? surface.canRedo?.() : surface.canUndo?.();
    const where = surface.where === "board" ? "on this board" : "in this document";
    button.disabled = !can;
    paintStatusItem(button.id, {
      icon,
      title: can ? `${Verb} the last change ${where}` : `Nothing to ${verb} ${where}`,
      shortcut: can ? verb : "",
    });
    return;
  }
  const top = stack[stack.length - 1];
  button.disabled = !top;
  paintStatusItem(button.id, {
    icon,
    title: top ? `${Verb}: ${top.label}` : `Nothing to ${verb}`,
    shortcut: top ? verb : "",
    //: The right-click gesture is named here because a hidden gesture is not a
    //: feature: the same reason the nav pair's tooltips name theirs.
    rest: top && !redo ? `right-click for the last ${stack.length}` : "",
  });
}

$("status-undo").addEventListener("click", performUndo);
$("status-redo").addEventListener("click", performRedo);


$("status-undo").addEventListener("contextmenu", (event) => {
  if (!undoStack.length || surfaceHistory()) return;
  event.preventDefault();
  openUndoHistoryMenu($("status-undo"));
});
wireLongPress($("status-undo"), () => {
  if (undoStack.length && !surfaceHistory()) openUndoHistoryMenu($("status-undo"));
});

document.addEventListener("mousedown", (event) => {
  const menu = $("undo-history-menu");
  if (!menu || menu.classList.contains("hidden")) return;
  if (!menu.contains(event.target) && event.target !== $("status-undo")) {
    menu.classList.add("hidden");
  }
});

// --- quick access: recent questions + most-used entries (Phase 5) -------------------

async function loadRecentQuestions() {
  const box = $("recent-questions");
  //: Shared with the dashboard's Recent questions widget (`cacheMs`), which
  //: asks for the same list in the same second at boot. Any write clears it.
  const questions = await apiJson("/chat/recent", { cacheMs: 30000 }).catch(() => []);
  box.replaceChildren();
  box.classList.toggle("hidden", questions.length === 0);
  if (questions.length === 0) return;
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = "Ask again:";
  box.appendChild(label);
  for (const question of questions) {
    //: The clock is what says "you asked this before" (INBOX 394 a): the chip
    //: is drawn like the suggestions beside it, so the icon carries the
    //: difference the fill used to.
    const short = question.length > 48 ? question.slice(0, 47) + "…" : question;
    const again = chip(`ph:clock-counter-clockwise ${short}`, "", () => {
      $("question").value = question;
      askQuestion();
    });
    again.title = question;
    box.appendChild(again);
  }
  ensureModule("askHistory").then(() => askAgainMenu(box, questions));
}

async function loadMostUsed() {
  const box = $("most-used-box");
  const list = $("most-used");
  const entries = await apiJson("/entries/most-accessed", { cacheMs: 30000 }).catch(() => []);
  list.replaceChildren();
  box.classList.toggle("hidden", entries.length === 0);
  for (const entry of entries) {
    const li = document.createElement("li");
    li.title = entry.content;
    const text = document.createElement("span");
    // Reported directly: a clip landing mid-token (`` `code` `` cut before
    // its closing backtick) left a stray `` ` `` sitting in the rendered
    // text: `safeMdSlice` drops the dangling marker instead of the plain
    // `slice(0, 25)` this used to do.
    //
    // Block syntax stripped first. renderInlineMarkdown is inline-only, so a
    // note beginning "# Groceries" rendered the literal "# Groceries", the
    // same gap the dashboard's mini-lists had, here too since this list uses
    // the same two-function combination.
    const flat = stripFrontmatter(entry.content).replace(/^\s*(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+\.\s+)/gm, "");
    const { text: sliced, truncated } = safeMdSlice(flat, 25);
    renderInlineMarkdown(text, sliced, [], true);
    if (truncated) text.appendChild(document.createTextNode("…"));
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = `×${entry.access_count}`;
    li.append(text, count);
    li.addEventListener("click", () => flashEntry(entry.id));
    list.appendChild(li);
  }
}

// --- model manager (Phase 3.5) ---------------------------------------------------

let modelStatus = null; // latest /models/status payload
//: The readouts settings-controls.js (a lazy bundle) draws, by name: it fills
//: them in when it loads, so a boot file calls `settingsReadouts.auto?.()`
//: rather than guarding a function that may not exist yet.
const settingsReadouts = {};

//: **The start-up choice, said once with Change** (the owner, 2026-10-07: on
//: a fresh install with five models it ran a llama3.2 it did not have). Once
//: per chosen model in this browser; Settings, Models keeps the why.
function sayChatModelChosen(status) {
  const why = status?.chat_model_chosen_why;
  if (!why || typeof toastAction !== "function") return;
  const key = `chatModelChosen:${status.chat_model}`;
  if (prefs.get(key)) return;
  if (!prefs.set(key, "1")) return;
  toastAction(`${aiNameNow()} now runs ${status.chat_model}: ${why}.`, "Change", () => openSettingsModal("models", "chat-model-select"));
}
// Has the status endpoint ever answered? "We haven't asked yet" and "we asked
// and got nothing" are both `modelStatus === null`, but they mean opposite
// things to the user: the first is normal for the first second of every
// startup, the second is a fault. Without this the indicator flashed red on
// every single page load before settling.
let statusEverAnswered = false;
//: Why the last poll has no status, for Settings' line (INBOX 435): "slow"
//: (the 8s budget ran out, usually a model server slow to answer), "down"
//: (the app's own server did not answer `/health` either), "error" (it did,
//: but the status call failed), or null.
let modelStatusProblem = null;
let suggestedCatalog = null; // loaded once, it never changes
let statusTimer = null;
//: The idle poll's own cadence, which doubles while nothing changes and
//: snaps back the moment something does: see the comment where it is read,
//: at the bottom of `refreshModelStatus`.
const STATUS_IDLE_MS = 30000;
const STATUS_IDLE_CEILING_MS = 120000;
let statusIdleDelay = STATUS_IDLE_MS;
//: `JSON.stringify` of the last payload. A string rather than a deep
//: compare because the payload is small, already came off the wire as one,
//: and "is this the same answer as last time" is the only question asked of
//: it.
let statusFingerprint = null;

//: Anything that means "the person is here, or something just changed":
//: the ladder starts again from the bottom. Called by the visibility
//: handler and by `kickBackgroundTaskPoll`, so a job started from this page
//: is never waiting out a two-minute idle delay.
function resetStatusCadence() {
  statusIdleDelay = STATUS_IDLE_MS;
}

// The Ollama embedding model offered as a one-click fallback when the
// built-in (sentence-transformers) engine can't load: asked for directly,
// after a real support-bundle report: the built-in engine needs
// sentence-transformers, which isn't bundled (see CLAUDE.md/requirements.txt
//, installing it has broken past sessions, and a packaged Windows build
// excludes torch on purpose), so a fresh install with no working Python on
// PATH for Settings -> Packages to fall back to has no way to make the
// built-in engine work at all. nomic-embed-text: small, well-known, and
// exactly what Settings -> Models' own "quick fix" sentence already named
// before this button existed.
const EMBEDDING_FALLBACK_MODEL = "nomic-embed-text";
let embeddingFallbackRunning = false;

function settingsOpen() {
  // The Models section lives inside the settings modal now (Wave A).
  return settingsModalOpen();
}

// --- every Settings change has its way back (settings-data.js, Recent changes) --
//
// The owner, 2026-10-11: "undo thing in settings??". Two choke points see every
// change, so no control has to remember: every `/preferences` answer passes the
// wrapper below (the last one kept as text, so a PUT can be diffed against it),
// and ai-tools.js reports a look key. All the rest (the diff, the list, the
// Undo) is the lazy settings-data.js, loaded only when a change is made while
// Settings is open: the boot scripts are at their gzip cap, and `apiJson` is
// wrapped here rather than edited at its twenty callers.
let settingsPrefsLast = null;
//: `settingsHistoryBusy` is set while an Undo or Redo writes, so its own write is
//: not noted again.
let settingsHistoryBusy = false;
{
  const apiJsonInner = apiJson;
  apiJson = async (path, options = {}) => {
    const data = await apiJsonInner(path, options);
    if (path === "/preferences") {
      const was = settingsPrefsLast;
      settingsPrefsLast = JSON.stringify(data);
      if (was && options.method === "PUT" && !settingsHistoryBusy && settingsOpen()) {
        ensureModule("settingsData").then(() => settingsPrefsSeen(JSON.parse(was), data));
      }
    }
    return data;
  };
}

function jobsRunning() {
  // Anything in `GET /tasks` counts, not just the two jobs `/models/status`
  // happens to carry. This used to read re-index and pulls only, so while a
  // caption, an image OCR or an autonomous pass was running the loop stayed
  // on its 10-second idle cadence, the status bar's job slot lagged by up
  // to ten seconds behind work that often does not last that long, and the
  // finish was noticed just as late. The two below are kept as their own
  // check rather than folded in: they come from a different payload, and a
  // `/tasks` call that fails leaves `backgroundTasks` empty while a pull is
  // demonstrably still running.
  if (backgroundTasks.length) return true;
  if (!modelStatus) return false;
  const reindexing = modelStatus.reindex && modelStatus.reindex.status === "running";
  const pulling = Object.values(modelStatus.pulls || {}).some(
    (job) => job.status === "running"
  );
  return reindexing || pulling;
}

// One polling loop for everything: slow when idle, fast while a
// download/re-index is running or the settings panel is open.
//: When `/tasks` was last asked, so the idle cadence below can ask it half as
//: often as `/models/status` (PLAN.md P1; MODERNISATION_AUDIT.md F2 measured
//: 14 requests in an idle minute on the Dashboard, status ×6, tasks ×6,
//: reminders ×2: against P1's gate of ≤ 4).
let backgroundTasksAskedAt = 0;
const TASKS_IDLE_MS = 60_000;

async function refreshModelStatus() {
  // Locked: no token, so every request is a guaranteed 401, noise in both
  // logs and a wake-up of the Python process for nothing. Re-arm cheaply and
  // let the unlock path call this itself (it does, after login).
  if (!authToken()) {
    clearTimeout(statusTimer);
    statusTimer = setTimeout(refreshModelStatus, 10000);
    return;
  }
  try {
    // silent: a poll must never trigger the lock screen (Wave O fix).
    // Fast-fail timeout: if the LLM hangs, the UI reflects offline in 8s.
    // Backend's own worst case is 2.5s (INSTALLED_REFRESH_BUDGET: the runner
    // call has its own thread and a poll serves the last answer past that),
    // so 8s leaves real headroom instead of racing it at the wire.
    modelStatus = await apiJson("/models/status", {
      silent: true,
      //: A timeout of a silent request (this poll is the only one that sets
      //: its own `AbortSignal.timeout`) is the "slow" state below, asked
      //: again on the next tick, so `api()` does not log it.
      signal: AbortSignal.timeout(8000)
    });
    statusEverAnswered = true;
    modelStatusProblem = null;
  } catch (err) {
    //: **A slow answer keeps the last good status** (OPEN ledger 1520): the
    //: Agent panel and the pill used to grey on every timeout and flicker
    //: back on the next poll. Only "slow" is flagged (`modelStatusProblem`),
    //: and Settings still says so. A fault or an unreachable server drops the
    //: status as before, so the pill shows the worst case.
    if (err?.name === "TimeoutError" || err?.name === "AbortError") modelStatusProblem = "slow";
    else {
      modelStatus = null; // locked or unreachable: pill shows the worst case
      const up = await fetch("/health", { signal: AbortSignal.timeout(3000) }).then((r) => r.ok).catch(() => false);
      modelStatusProblem = up ? "error" : "down";
    }
  }
  //: **The feature rows ride every poll, not only Settings.** They used to be
  //: read only when Settings rendered, so until Settings had been opened once
  //: the ⋯ sheet said "Models aren't available yet" and a picker in a
  //: surface had nothing to show. The poll already carries them.
  if (modelStatus && Array.isArray(modelStatus.feature_models)) {
    featureModelRows = modelStatus.feature_models;
    featureModelNames = (modelStatus.installed_models || []).map((m) => m.name);
  }
  syncFeatureModelSelects();
  renderAiPill();
  syncModelGatedControls();
  sayChatModelChosen(modelStatus);
  // The status bar's job slot rides this loop rather than starting one of its
  // own, so it inherits the whole cadence: one second while something is
  // running, thirty when idle, two minutes behind a hidden tab. Idle, `/tasks`
  // is asked every other tick: a job that starts from this page kicks the poll
  // itself (`kickBackgroundTaskPoll`), so an idle minute only has to notice a
  // job started somewhere else, and once a minute is soon enough for that.
  const idle = !jobsRunning() && !settingsOpen();
  if (!idle || Date.now() - backgroundTasksAskedAt >= TASKS_IDLE_MS) {
    backgroundTasksAskedAt = Date.now();
    await refreshBackgroundTasks();
  }
  if (settingsOpen()) renderSettings();

  clearTimeout(statusTimer);
    // Off while the tab is hidden; 30s when idle (the status changes in
    // minutes, and every tick wakes the model runner). **Doubling while the
    // answer is byte-identical** (INBOX 266 item 7, gate: at most 2 requests an
    // idle minute); any change, a return to the tab, Settings or a job drops it
    // back to 30s. Cost: Ollama starting is seen in up to two minutes on an idle
    // laptop.
  const fingerprint = JSON.stringify(modelStatus);
  if (fingerprint !== statusFingerprint) {
    statusFingerprint = fingerprint;
    statusIdleDelay = STATUS_IDLE_MS;
  } else if (!jobsRunning() && !settingsOpen() && !document.hidden) {
    statusIdleDelay = Math.min(statusIdleDelay * 2, STATUS_IDLE_CEILING_MS);
  }
  const delay = jobsRunning()
    ? 1000
    : document.hidden
      ? 120000
      : settingsOpen()
        ? 3000
        : statusIdleDelay;
  statusTimer = setTimeout(refreshModelStatus, delay);
}

// Refresh immediately when the user returns to the tab, so a status that went
// stale while hidden snaps up to date instead of waiting out the long delay.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    resetStatusCadence();
    refreshModelStatus();
  }
});

// Controls that only work with a chat model running are disabled with the
// reason, before the effort, not failed after it. **The list lives in the
// markup** (INBOX 203): `data-needs-model="<why>"` on the control, so a
// control added later cannot be forgotten here; `tests/test_frontend_ids.py`
// holds the inventory. Never marked: Save, Ask, search, tags, categories, the
// graph, reminders, documents, the meeting Save and "Map from notes"
// (`WORKS_WITHOUT_A_MODEL`): they work without a model and must not look
// diminished by its absence.

//: **The one sentence a disabled AI control says** (CHAT_PLAN.md decision 11:
//: "every AI control is visible, disabled, with a tooltip 'Connect a model in
//: Settings' and a one-click link"). It named Ollama before,
//: which is one of the three providers this app supports and tells somebody
//: running llama.cpp or an OpenAI-compatible server to start the wrong thing. Settings is where all three are set up, so Settings is what a
//: control points at.
const AI_OFFLINE_HINT = "Connect a model in Settings";

//: Unknown status (locked, still loading) is available: better to let a click
//: fail than to grey out a working button on a slow start.
//:
//: **Off means no model can answer, not only no server** (ledger 1521;
//: INBOX 778: a reachable server with no chat model installed answers
//: nothing). `model_ready` is the server's own verdict; the Needle engine
//: (`tools_engine`) answers without one, so it keeps the gate open.
function aiIsOff() {
  if (!modelStatus) return false;
  if (modelStatus.ollama_running === false) return true;
  return modelStatus.model_ready === false && !modelStatus.tools_engine;
}

//: **Why this restores rather than enables.** The status poll runs this every
//: tick, one second while a job is going, and some of the gated controls have a
//: busy state of their own: Save notes is disabled until the extract has notes
//: to save and again while it saves, the guide's Ask is disabled for the length
//: of a question. A plain `disabled = off` would hand all of those back mid-run
//: on the next tick. So the gate records that it was the one that closed a
//: control and reopens only what it closed.
//: **A gated control that answers when pressed** (DOCUMENTS 24 row 3, the
//: CHAT_PLAN gating pattern). One marked `data-model-offer` is not disabled
//: with no model: it is `aria-disabled`, still a Tab stop, and a press opens a
//: popover saying why, what still works here (the attribute's own line) and
//: one way on, Set up a model. A disabled button explains nothing to someone
//: who presses it: the no-model sweep counted the documents' two as dead.
function closeModelGate(control) {
  if (control.dataset.modelOffer !== undefined) {
    control.setAttribute("aria-disabled", "true");
    return;
  }
  if (control.disabled) return;
  control.dataset.modelGated = "1";
  control.disabled = true;
}

function openModelGate(control) {
  if (control.dataset.modelOffer !== undefined) control.removeAttribute("aria-disabled");
  if (!control.dataset.modelGated) return;
  control.disabled = false;
  delete control.dataset.modelGated;
}

function openModelOffer(control) {
  closeHelpPopovers();
  const panel = document.createElement("div");
  panel.className = "help-body model-offer";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Needs a model");
  const why = document.createElement("p");
  why.textContent = `${control.dataset.needsModel}, and no model is connected. ${control.dataset.modelOffer}`.trim();
  const setUp = smallButton("ph:plugs Set up a model", "Open Settings at Models, where a local or remote model is connected", () => {
    entry.close();
    openSettingsModal("models");
  });
  setUp.classList.add("primary");
  panel.append(why, setUp);
  const entry = {
    panel,
    trigger: control,
    close() {
      openHelpPopovers.delete(entry);
      panel.remove();
      control.setAttribute("aria-expanded", "false");
    },
  };
  panel.style.visibility = "hidden";
  panel.classList.add("help-popover");
  (control.closest("dialog[open]") || document.body).appendChild(panel);
  panel.addEventListener("click", (event) => event.stopPropagation());
  openHelpPopovers.add(entry);
  control.setAttribute("aria-expanded", "true");
  placeHelpPopover(panel, control);
  setUp.focus();
}

//: Capture, so the control's own handler (which would start the AI act)
//: never sees a press made while the gate is shut.
document.addEventListener(
  "click",
  (event) => {
    const control = event.target.closest?.('[data-model-offer][aria-disabled="true"]');
    if (!control) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openModelOffer(control);
  },
  true
);

function syncModelGatedControls(status = modelStatus) {
  const off = status ? status.ollama_running === false : false;
  for (const control of document.querySelectorAll("[data-needs-model]")) {
    const reason = control.dataset.needsModel;
    if (off) {
      closeModelGate(control);
      //: `=== undefined`, not a truthiness test, and the saved copy is dropped
      //: once it has been put back. A control whose own title is empty saves
      //: "" here, and `!""` is true, so on the next tick of the poll (one
      //: second while a job runs) the gated sentence was saved over the empty
      //: original and then restored as if it were the original: nine of the
      //: fifteen kept "Connect a model in Settings" as their tooltip after the
      //: model came back. Measured: 9 of 15 wrong, now 0.
      if (control.dataset.enabledTitle === undefined) {
        control.dataset.enabledTitle = control.title || "";
      }
      control.title = `${reason}. ${AI_OFFLINE_HINT}.`;
    } else {
      openModelGate(control);
      if (control.dataset.enabledTitle !== undefined) {
        control.title = control.dataset.enabledTitle;
        delete control.dataset.enabledTitle;
      }
    }
    control.classList.toggle("ai-unavailable", off);
  }
  //: With no model server answering, the per-feature models and the sampling
  //: settings have nothing to act on (owner, 2026-10-12): hidden, unless a
  //: feature already has an override of its own, which must stay visible so it
  //: can be cleared (WORLD_CLASS_PLAN 20).
  const holdsOverride = Number(status?.feature_models_overridden || 0) > 0;
  $("feature-models-config")?.classList.toggle("hidden", off && !holdsOverride);
  const sampling = $("sampling-box");
  (sampling?.parentElement?.classList.contains("fold-help-wrap") ? sampling.parentElement : sampling)?.classList.toggle("hidden", off);
  //: The badge is a span, not a button, so `disabled` does nothing to it
  //: (see its own comment in `renderTimelineEntry`). Explicitly hidden here so
  //: a badge drawn while the model was online doesn't sit on screen as a
  //: broken promise once it drops.
  for (const badge of document.querySelectorAll(".untagged-ai")) {
    badge.style.display = off ? "none" : "";
  }
  //: The link half of decision 11. A tooltip on a disabled control is read by
  //: somebody who already suspects the answer; a person who does not know why
  //: half the app went quiet needs a sentence they can act on, in the place
  //: they are looking. Two surfaces, because those are the two that are
  //: nothing but AI: Ask keeps working (it falls back to the search results
  //: beside it) and says so, the popup agent cannot and says that.
  renderAiOfflineNotice(
    $("ask-offline"),
    "No model connected. Ask shows the matching records below.",
    { dismissible: true, detail: "Ask answers from your notes alone until one is connected." }
  );
  //: The agent with no model runs acts and readings (AGENT_SKILLS_REFORM
  //: "Deepened 2026-10-10" row 1, `ai/starter_acts.py`), so the line says
  //: what a model adds rather than that nothing runs.
  renderAiOfflineNotice(
    $("command-palette-offline"),
    "No model connected. The agent runs acts and reads your notes.",
    { dismissible: true, detail: "Reminders, notes, tags, links and the day's changes work now. Open questions and drafting need a model." }
  );
  //: The Chat tab (INBOX 266 part 1, then 725): with no model a message is
  //: answered from the notes by the composer, so the box stays open and the
  //: line says what a model would add rather than that nothing answers.
  renderAiOfflineNotice(
    $("chat-offline"),
    "No model connected. Chat answers from your notes.",
    { dismissible: true, detail: "Chat quotes your notes until one is connected. A model adds AI answers and Agent mode." }
  );
  //: And the writing desk, which is the third surface that is nothing but
  //: Atlas: with no model it cannot draft at all, and before this the only
  //: thing that said so was a title on a button that could not be pressed.
  renderAiOfflineNotice(
    $("draft-offline"),
    "No model connected, so nothing can be drafted. The rest of this tab works."
  );
  //: UX-12: any other AI-only widget names its own line.
  for (const line of document.querySelectorAll("[data-offline-line]")) renderAiOfflineNotice(line, line.dataset.offlineLine);
  //: A field that still works with no model says what it does then.
  for (const field of document.querySelectorAll("[data-offline-placeholder]")) {
    if (field.dataset.onlinePlaceholder === undefined) field.dataset.onlinePlaceholder = field.placeholder;
    field.placeholder = off ? field.dataset.offlinePlaceholder : field.dataset.onlinePlaceholder;
  }
  //: Surfaces built in script (the inline AI bar) follow the change live.
  if (syncModelGatedControls.off !== off) {
    syncModelGatedControls.off = off;
    document.dispatchEvent(new CustomEvent("mm-model-gate", { detail: { off } }));
  }
  syncAgentPaletteAvailability();
  renderChatModeSeg();
}

//: **A control built after the last poll is gated when it arrives** (the
//: owner, 2026-10-10: "I can still activate skills ... when I have no model
//: running"). The poll applies `data-needs-model` every tick, but idle that is
//: thirty seconds, and the chat dock's Skills button is built by skills.js when
//: the dock first draws: it stayed pressable for up to half a minute after
//: boot (measured: enabled 2.5 s in, with the attribute set). Watching for added
//: nodes covers every lazily built control, including ones not written yet,
//: rather than asking each builder to remember a call. The records of one
//: task arrive together, so one gate pass however many nodes land.
new MutationObserver((records) => {
  if (modelStatus && records.some((r) => [...r.addedNodes].some((n) => n.querySelector?.("[data-needs-model]") || n.matches?.("[data-needs-model]")))) syncModelGatedControls();
}).observe(document.body, { childList: true, subtree: true });

//: **A banner can be closed for the session** (INBOX 732: "a way to
//: temporarily hide these no ai popups, they can appear again when the user
//: starts a new app session"). Kept in `sessionStorage`, which a new app
//: session starts empty, with a plain Set beside it for a profile that
//: refuses storage. Never `localStorage`: that would be for good.
const AI_OFFLINE_DISMISSED_KEY = "aiOfflineDismissed";
const aiOfflineDismissedNow = new Set();

//: The person's own switch (Settings, Models): the banners never show.
function aiOfflineNoticeHidden() {
  return prefs.get("hideOfflineNotice", null) === "on"; // prefs.get never throws
}

function aiOfflineDismissed(id) {
  try {
    return aiOfflineDismissedNow.has(id) || JSON.parse(sessionStorage.getItem(AI_OFFLINE_DISMISSED_KEY) || "[]").includes(id);
  } catch {
    return false;
  }
}

function dismissAiOffline(id) {
  aiOfflineDismissedNow.add(id);
  try {
    sessionStorage.setItem(AI_OFFLINE_DISMISSED_KEY, JSON.stringify([...aiOfflineDismissedNow]));
  } catch { /* memory alone still lasts until the window closes */ }
}

//: One row (DESIGN.md, "A notice"): an icon, one short sentence, the button
//: that fixes it, then the close when it has one. The container carries
//: `.notice`; what a surface says beyond the sentence goes in `detail`, which
//: becomes the button's title (INBOX 767: the long sentence was the ugly part).
//: Rebuilt
//: rather than toggled because the status poll calls this every tick and a
//: stale sentence is worse than none. `dismissible` adds the close (DESIGN.md,
//: "A notice that can be closed"): a dismissed one stays hidden for the session.
function renderAiOfflineNotice(container, what, { dismissible = false, detail = "" } = {}) {
  if (!container) return;
  const show = aiIsOff() && !aiOfflineNoticeHidden() && !(dismissible && aiOfflineDismissed(container.id));
  //: Left alone when nothing changed: the poll must not close the caret's open menu.
  if (show && container._k === what + detail) return;
  container._k = show ? what + detail : "";
  container.replaceChildren();
  container.classList.toggle("hidden", !show);
  if (!show) return;
  //: The icon is the container's first child, which is where `.notice > .ph`
  //: styles it; `setLabel` on the container builds exactly that.
  setLabel(container, "ph:plugs");
  const text = document.createElement("span");
  text.className = "ai-offline-text";
  text.textContent = what;
  const link = document.createElement("button");
  link.type = "button";
  link.className = "ghost small";
  link.textContent = AI_OFFLINE_HINT;
  link.title = `Open Settings at Models, where a local or remote model is connected.${detail ? ` ${detail}` : ""}`;
  link.addEventListener("click", () => openSettingsModal("models"));
  //: **Connect a model is a split button** (INBOX 904 B05): offline-split.js wraps
  //: it and adds the caret that hides these notices.
  lazyScript("/js/offline-split.js").then((ok) => ok && aiOfflineSplit(link));
  container.append(text, link);
  if (!dismissible) return;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "ghost small icon-only";
  close.dataset.dismiss = "notice";
  setLabel(close, "ph:x");
  close.title = "Hide this until you reopen the app";
  close.setAttribute("aria-label", "Hide this notice until you reopen the app");
  close.addEventListener("click", () => {
    dismissAiOffline(container.id);
    container.replaceChildren();
    container.classList.add("hidden");
  });
  container.append(close);
}

//: The popup agent no longer closes with no model (row 1 above): every
//: starter and any act the reading knows runs without one, so its field and
//: starters stay open and only say, on hover, what is answered how.
function syncAgentPaletteAvailability() {
  const input = $("command-palette-input");
  if (input) input.title = aiIsOff() ? "No model: acts and readings from your notes" : "";
}

// What the AI is doing, as one decision.
//
// Three levels, and the boundary between them is deliberate. This app is built
// to degrade gracefully, so "no AI at all" is a supported way to run it, not a
// fault: it is amber, not red. Red is reserved for something that is actually
// broken: a model that failed to load, or a server we can't reach. Colouring a
// normal offline setup red would train the user to ignore the indicator.
//
//   idle  … grey    haven't heard back yet, says nothing either way
//   ok    ✓ green   everything the AI can do is available
//   off   AI sparkle, slashed, grey: no model connected, the offline way to run
//   warn  ! amber   loading or rebuilding, app works
//   error ✕ red     something is broken and won't fix itself
function aiStatusState() {
  if (!modelStatus) {
    // The first poll of every page load lands here for a moment. Reporting
    // that as a fault would flash red on every startup and teach the user
    // that red means nothing, so an unanswered *first* request is its own
    // quiet state, and only a request that has failed after we have already
    // had an answer counts as the server going away.
    if (!statusEverAnswered) {
      return {
        level: "idle",
        title: "Checking…",
        detail: "Asking the app what Atlas is doing. This takes a moment.",
      };
    }
    return {
      level: "error",
      title: "Can't reach Tessellate",
      detail:
        "The app can't read its own status, which usually means the server " +
        "stopped. Your notes are safe on disk.",
    };
  }
  const chatReady = modelStatus.ollama_running;
  const searchReady = modelStatus.embedding_ready;

  if (modelStatus.reindex && modelStatus.reindex.status === "running") {
    return {
      level: "warn",
      title: "Rebuilding the search index",
      detail:
        "Searching by word works while this runs. Searching by meaning comes " +
        "back when it finishes.",
    };
  }
  if (!searchReady && modelStatus.embedding_warming) {
    return {
      level: "warn",
      title: "Search AI is warming up",
      detail:
        "Searching by word works now. Searching by meaning becomes available " +
        "once the model has loaded.",
    };
  }
  if (!searchReady && modelStatus.embedding_error) {
    // "Broken" and "still loading" looked identical before: the old pill said
    // "warming up…" forever when the model had actually failed.
    return {
      level: "error",
      title: "Search AI didn't load",
      detail:
        `${modelStatus.embedding_error}\n\nSearching by word still works, and ` +
        "notes, tags, reminders and the graph are unaffected. Settings → Logs " +
        "has the details.",
    };
  }
  if (chatReady && searchReady) {
    return {
      level: "ok",
      title: "AI ready",
      detail: "Chat, auto-filing and search by meaning are all available.",
    };
  }
  // Everything below leads with what still WORKS. Announcing a fault and
  // pointing at a log reads as "the app is broken" when in fact only the
  // optional half is missing.
  //: **"off", not "warn"** (INBOX 472, the first-run walk): this is the
  //: supported way to run, and an amber "!" (a 44px amber circle in the
  //: phone's top bar) was the loudest thing on a new person's first screen.
  //: Neutral, with the ring Settings, Models draws beside "isn't running".
  if (!chatReady && searchReady) {
    return {
      level: "off",
      title: "Notebook ready · chat AI off",
      detail:
        "Notes, search, tags, reminders and the graph all work. Connect a " +
        "model in Settings, Models to add chat and auto-filing.",
    };
  }
  if (chatReady && !searchReady) {
    return {
      level: "warn",
      title: "Word search on · AI search warming",
      detail:
        "Searching by word works now; searching by meaning becomes available " +
        "once the embedding model has loaded.",
    };
  }
  return {
    level: "off",
    title: "Notebook ready · AI off",
    detail:
      "Writing, searching, tagging, reminders, documents and the graph all " +
      "work without any AI. Connect a model in Settings, Models to add chat, " +
      "auto-filing and search by meaning.",
  };
}

// The glyph is not decoration. Colour alone fails for the ~8% of men with a
// colour vision deficiency, and fails everyone in high-contrast mode, so the
// shape carries the same meaning the colour does.
// "…" for connecting rather than a spinner: a spinner has to be animated to
// read as one, and under prefers-reduced-motion a frozen spinner looks like a
// rendering fault. The ellipsis says "waiting" while perfectly still.
const AI_STATUS_GLYPH = { idle: "…", ok: "✓", warn: "!", error: "✕", off: "" };

//: **"AI off" is the app's AI sparkle with a slash** (INBOX 656, the owner:
//: "can the no ai available ai status icon be better??"). It was a hollow
//: ring, which said nothing; the sparkle is what every AI control here wears
//: (Ask, Refine, the agent), and the slash, cut clear of it by a mask so it
//: reads at 14px, says it is not connected. It stays in the muted ink on the
//: chip, never amber: the notebook is fine, which is the card's first words.
//: An svg in `currentColor`, not the icon font plus a pseudo-element, so it
//: costs the boot stylesheet nothing and centres by the dot's own grid.
function aiOffGlyph() {
  const ns = "http://www.w3.org/2000/svg";
  const make = (tag, attrs, parent) => {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (parent) parent.appendChild(el);
    return el;
  };
  const svg = make("svg", { class: "ai-off-glyph", viewBox: "0 0 16 16", width: "14", height: "14", fill: "none", stroke: "currentColor", "stroke-width": "1.5", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" });
  const mask = make("mask", { id: "ai-off-gap", maskUnits: "userSpaceOnUse", x: "0", y: "0", width: "16", height: "16" }, make("defs", {}, svg));
  make("rect", { width: "16", height: "16", fill: "white", stroke: "none" }, mask);
  make("path", { d: "M2.5 2.5L13.5 13.5", stroke: "black", "stroke-width": "3.4" }, mask);
  make("path", { d: "M8 1.4Q9.9 6.1 14.6 8Q9.9 9.9 8 14.6Q6.1 9.9 1.4 8Q6.1 6.1 8 1.4Z", mask: "url(#ai-off-gap)" }, svg);
  make("path", { d: "M2.5 2.5L13.5 13.5" }, svg);
  return svg;
}

//: **How the last answer went, on the AI dot** (WORLD_CLASS_PLAN, Placed
//: 2026-09-09 item 99 (c)): the model, the time it took and how much of its
//: window the question filled, set by the chat when a turn ends.
let lastAnswerFacts = null;

function lastAnswerLine() {
  const facts = lastAnswerFacts;
  if (!facts || !facts.ms) return "";
  const parts = [facts.model, `${(facts.ms / 1000).toFixed(1)} s`];
  if (facts.used && facts.window) parts.push(`${Math.min(100, Math.round((facts.used / facts.window) * 100))}% of its window`);
  return `Last answer: ${parts.filter(Boolean).join(", ")}.`;
}

function renderAiPill() {
  const button = $("ai-status");
  if (!button) return;
  const state = aiStatusState();
  button.dataset.level = state.level;
  //: "Checking" is three dots drawn by CSS, not "…": an ellipsis sits on the
  //: baseline in every font and the icon font's dots sit above the middle,
  //: 3px off either way (INBOX 435, measured); a box of known size is
  //: centred by the dot's own grid. ✓, ! and ✕ are within half a pixel.
  const dot = button.querySelector(".ai-status-dot");
  if (state.level === "off") {
    if (!dot.querySelector(".ai-off-glyph")) dot.replaceChildren(aiOffGlyph());
  } else dot.textContent = state.level === "idle" ? "" : AI_STATUS_GLYPH[state.level];
  // The button's own name for screen readers and for the native tooltip, so
  // the information is reachable without opening anything.
  const summary = `AI status: ${state.title}`;
  $("ai-status-label").textContent = summary;
  // button.title = `${state.title}\n\n${state.detail}`;
  $("ai-status-title").textContent = state.title;
  const last = lastAnswerLine();
  $("ai-status-detail").textContent = last ? `${state.detail} ${last}` : state.detail;
  renderChatActiveModelBadge();
  nudgeEmbeddingProblem();
}

//: **A broken search engine is said where the person is, once** (owner,
//: packaged app: "I didnt have sentence transformers installed ... I
//: encountered errors and I saw no popup or anything to suggest that I
//: switch to nomic-embed-text or install sentence transformers"). The fix
//: sentence and its one-click button lived only in Settings, Models, which
//: nobody opens to find out why search feels dull. So the first poll that
//: carries `embedding_error` raises a toast with the way to fix it and leaves
//: the same in the bell, keyed by the error so it is said once per problem,
//: not once per poll.
let embeddingNudgeSaid = "";
function nudgeEmbeddingProblem() {
  const error = modelStatus?.embedding_error;
  if (!error || error === embeddingNudgeSaid) return;
  embeddingNudgeSaid = error;
  const installing = /being installed/.test(error);
  const title = installing ? "Search by meaning is being installed" : "Search by meaning is not working";
  const detail = installing
    ? "Search uses keywords until it finishes. Or pick nomic-embed-text in Settings, Models."
    : `${error}. Settings, Models can switch it to ${EMBEDDING_FALLBACK_MODEL} or install the package.`;
  recordNotification({
    kind: "assist",
    title,
    detail,
    key: `embedding:${error}`,
    action: { settings: "models" },
  });
  if (!installing) toastAction(`${title}. Search is using keywords for now.`, "Fix it", () => openSettingsModal("searchindex", "embedding-model-select"), { record: false });
}

// --- the status bar (§36D) ---------------------------------------------------
//
// Five items, and the roadmap's own test for what may be here: each one is
// either a state worth knowing at a glance or a command you use constantly.
// Anything else is a permanent strip of decoration, so anything added later
// should have to displace one of these rather than sit beside them.
//
// **Nothing here polls.** Every value arrives on a loop that already existed:
// the AI state and the background job on `refreshModelStatus`, the reminder
// counts wherever the tab badge is painted, the notebook size when the notes
// are loaded. That is deliberate and it is not a micro-optimisation, a
// reminder poll running on two timers is a bug this project has already had
// and had to find in a browser, and a bar with five values is five chances to
// repeat it.

//: What the reminder poll last saw. Two numbers rather than a list: the bar
//: needs counts, and holding the reminders themselves here would be a second
//: copy of state the Reminders tab already owns.
let reminderCounts = { open: 0, due: 0 };

//: The running background jobs, straight from GET /tasks. Not reassembled from
//: `modelStatus`, routes_tasks.py exists precisely because the frontend used
//: to build this list out of the two jobs that happened to be in the status
//: payload, and everything else (the embedding warm-up, the SearXNG install)
//: was invisible.
let backgroundTasks = [];

//: ⌘ on a Mac, Ctrl everywhere else. `userAgentData` where it exists because
//: `navigator.platform` is deprecated and lies inside some embedded shells;
//: the fallback is what the desktop window still answers.
const STATUS_META_KEY = SHORTCUT_MAC ? "⌘K" : "Ctrl K";

// One item: an icon, a number, and a word. The number is bold and tabular so
// the row does not twitch sideways as counts change, a status bar that moves
// while you are reading it is the thing the header was rebuilt to stop doing.
function paintStatusItem(id, { icon, value, label, title, tone = "", shortcut = "", rest = "" }) {
  const button = $(id);
  if (!button) return;
  //: `shortcut` is a `DEFAULT_SHORTCUTS` action: its current binding goes on
  //: the tooltip (INBOX 701), and only when there is a tooltip to put it on.
  if (title && shortcut) title = shortcutTitle(title, shortcut);
  //: A gesture named after the chord ("right-click for the last 3").
  if (title && rest) title = `${title}: ${rest}`;
  button.replaceChildren();
  if (icon) {
    const glyph = document.createElement("span");
    setLabel(glyph, icon);
    glyph.setAttribute("aria-hidden", "true");
    button.appendChild(glyph);
  }
  if (value !== undefined && value !== null) {
    const strong = document.createElement("b");
    strong.textContent = String(value);
    button.appendChild(strong);
  }
  if (label) {
    //: A space between the number and its word, not drawn (a flex row drops
    //: it) but read: "29notes" is what a tool takes the visible text to be.
    if (value !== undefined && value !== null) button.append(" ");
    const text = document.createElement("span");
    text.textContent = label;
    button.appendChild(text);
  }
  button.title = title || "";
  // The title doubles as the accessible name, exactly as `smallButton` already
  // does: without this the three icon-only status buttons (Undo, Redo,
  // Commands) announce as a bare "button" to a screen reader. The ones that
  // also paint a `value`/`label` have real text and do not need it, but
  // setting it uniformly keeps the two from drifting apart.
  //: WCAG 2.5.3, the visible words are part of the name ("29 notes: Your
  //: notebook..."), which axe's label-content-name-mismatch found on the
  //: notes and reminders counts.
  const shown = [value, label].filter((part) => part !== undefined && part !== null && part !== "").join(" ");
  if (title) button.setAttribute("aria-label", shown ? `${shown}: ${title}` : title);
  else button.removeAttribute("aria-label");
  button.classList.toggle("status-due", tone === "due");
}

function renderStatusBar() {
  if (!$("status-bar")) return;

  // The notebook's size, from the list the app has already loaded rather
  // than from /insights/stats: costs nothing, and is exact once loadEntries
  // finishes. GET /entries pages for a large notebook now (ENTRIES_PAGE_SIZE
  // above), so for the first moment after unlocking a several-thousand-note
  // notebook this can undercount while later pages are still landing in the
  // background: self-corrects within a render or two, and is still a more
  // honest number than showing nothing while it catches up. Before the first
  // load it says nothing rather than "0 notes", which would be a lie for the
  // second it is up.
  paintStatusItem("status-notes", {
    icon: "ph:note-pencil",
    //: Drafts left out, as the Notes list and its sidebar count leave them
    //: out: three places saying three numbers was the owner's "do I have
    //: 29, 30, or 31 notes?".
    value: entriesEverLoaded ? noteCountExcludingDrafts() : "–",
    label: noteCountExcludingDrafts() === 1 && entriesEverLoaded ? "note" : "notes",
    title: "Your notebook: click to browse it",
  });

  // Due, or open. The same choice the dashboard's tile makes, and it has to
  // stay the same choice: two counters visible at once that count differently
  // is worse than either alone.
  const { open, due } = reminderCounts;
  paintStatusItem("status-reminders", {
    icon: due ? "ph:alarm" : "ph:check-circle",
    value: due || open,
    label: due ? "due" : "open",
    title: due
      ? `${due} reminder${due === 1 ? "" : "s"} due now`
      : `${open} open reminder${open === 1 ? "" : "s"}`,
    tone: due ? "due" : "",
  });

  // The job slot appears only while there is one. Where several run at once it
  // shows the first, /tasks orders them newest-concern-first, and says how
  // many are behind it, because a bar is one line and a queue is not.
  const task = backgroundTasks[0];
  const slot = $("status-task");
  slot.classList.toggle("hidden", !task);
  if (task) {
    //: "2 running: Answering 'what is a mouse'" (INBOX 805): how many, and
    //: the newest concern by name. The ring is the shared working mark
    //: (`ph:spin`), which only breathes under reduced motion.
    const count = backgroundTasks.length;
    paintStatusItem("status-task", {
      icon: "ph:spin",
      value: count,
      label: `running: ${task.label}`,
      title:
        backgroundTasks.map((t) => `${t.label}${t.detail ? `, ${t.detail}` : ""}`).join("\n") +
        "\n\nClick to open Activity, where each run shows its lines and can stop.",
    });
  }

  // The palette already exists and is already on Ctrl/⌘-K; what it did not
  // have was anywhere on screen saying so. A shortcut nobody can see is a
  // shortcut only the person who wrote it uses.
  const command = $("status-command");
  command.replaceChildren();
  const key = document.createElement("span");
  key.className = "status-key";
  key.textContent = shortcutHint("palette") || STATUS_META_KEY;
  const word = document.createElement("span");
  word.textContent = "Commands";
  command.append(key, word);
  command.title = shortcutTitle("Search everything and jump anywhere", "palette");

  // Same reasoning one control along: the popup agent works from every tab
  // and had nothing on screen saying it exists. Reported as exactly that, 
  // it needed to be reachable from the tools popup, the palette, Settings
  // "and maybe even the bottom status bar".
  const agent = $("status-agent");
  if (agent) {
    agent.replaceChildren();
    const glyph = document.createElement("i");
    glyph.className = "ph ph-strategy";
    glyph.setAttribute("aria-hidden", "true");
    const word = document.createElement("span");
    //: UX-07: the name of the dialog it opens; "Ask" is Notes' and Chat's.
    word.textContent = "Agent";
    agent.append(glyph, word);
    //: Icon-only at every width (INBOX 618): the word is clipped by CSS, and
    //: names the button here so a screen reader and voice control keep it.
    agent.setAttribute("aria-label", "Agent");
    //: The chord comes from the table (`shortcutTitle`), not from a modifier
    //: guessed here: `STATUS_META_KEY` is the whole "Ctrl K"/"⌘K" hint, and
    //: appending to it once produced "Ctrl K+Shift+A", no shortcut at all.
    agent.title = shortcutTitle("Ask the agent anything, from any tab", "askAgent");
  }

  //: The Guide, built the same way one control along (INBOX 207): it left the
  //: header cluster with the agent's button, and the pair belongs together, one does
  //: things to your notes and the other explains the app. A compass rather
  //: than the header's '?', because a '?' beside a labelled word reads as
  //: help about the word.
  //: Find anything, one along again. A magnifying glass rather than a word
  //: alone, because the bar's other two are glyph-plus-word and a lone word
  //: here would read as a label for the Guide beside it.
  const find = $("status-find");
  if (find) {
    find.replaceChildren();
    const glyph = document.createElement("i");
    glyph.className = "ph ph-magnifying-glass";
    glyph.setAttribute("aria-hidden", "true");
    const word = document.createElement("span");
    word.textContent = "Find";
    find.append(glyph, word);
    //: Icon-only at every width (INBOX 618): the word is clipped by CSS, and
    //: names the button here so a screen reader and voice control keep it.
    find.setAttribute("aria-label", "Find");
    //: Built the same way the agent's hint two controls up is.
    find.title = shortcutTitle("Search everything you keep, and the app itself", "findAnything");
  }

  const guide = $("status-guide");
  if (guide) {
    guide.replaceChildren();
    const glyph = document.createElement("i");
    glyph.className = "ph ph-compass";
    glyph.setAttribute("aria-hidden", "true");
    const word = document.createElement("span");
    //: **The dock says the scope, the tooltip says who answers.** This read
    //: `GUIDE_NAME` ("Atlas") and sat next to "Ask", so the bar offered two
    //: buttons that both mean "talk to the AI" and neither said which one
    //: knows about your notes and which one knows about the app. A name is
    //: also the one label here that a setting can invalidate: the persona is
    //: renameable, so a button spelling it either goes stale or stops reading
    //: as help. The word is the scope; the name is on hover, where the panel
    //: it opens introduces Atlas anyway.
    word.textContent = "Guide";
    const guideName = typeof GUIDE_NAME === "string" ? GUIDE_NAME : "Atlas";
    guide.append(glyph, word);
    guide.setAttribute("aria-label", "Guide");
    guide.title = shortcutTitle(`Ask ${guideName} how this app works, from any tab`, "askAtlas");
  }
}

// Hover is handled in CSS. This is the click half, needed for touch, where
// there is no hover, and for keyboards, where there is no pointer.
function toggleAiStatusPopup(force) {
  const button = $("ai-status");
  const popup = $("ai-status-popup");
  if (!button || !popup) return;
  const open = force !== undefined ? force : !button.classList.contains("pinned");
  button.classList.toggle("pinned", open);
  button.setAttribute("aria-expanded", String(open));
  // Visibility, not the `hidden` attribute: `hidden` is display:none, which
  // the CSS hover rule would then have to fight. The stylesheet owns whether
  // the popup is shown; this only records that it has been pinned open.
  popup.classList.toggle("pinned", open);
}


// What to call the backend on screen. The whole UI was written when there was
// only Ollama, and the word is in a dozen strings; this is the one place that
// decides, so the rest read from it (§6).
// The Chat / Agent pair. The hidden checkbox stays the single source of truth
//, every other reader in the app already consults it, and a second store for
// the same fact is how two of them end up disagreeing. These buttons just show
// it and set it.
//: Whether Agent mode can run right now: a model that can answer
//: (`model_ready`: a reachable server is not enough, INBOX 778), or the Needle
//: extra on disk (decision 22). No status yet or a failed poll counts as
//: neither. One reader, so the segment, the "Ask about this" switch and the Web
//: toggle's title cannot disagree.
function agentModeAvailable() {
  return modelStatus?.model_ready === true || !!modelStatus?.tools_engine;
}

function renderChatModeSeg() {
  //: **Agent mode needs something that can call tools** (INBOX 725, the
  //: owner: "maybe agent mode should be disabled though unless needle is used
  //: to call tools without an ai"). With no model and no Needle it is greyed
  //: with its reason and Ask shows as the mode in use, without touching the
  //: saved choice, which comes back with the model. With Needle ready it runs
  //: there, and says so.
  const engine = modelStatus?.tools_engine || null;
  const gated = !agentModeAvailable();
  const agentButton = document.querySelector('#chat-mode-seg [data-chat-mode="agent"]');
  if (agentButton) {
    if (agentButton.dataset.enabledTitle === undefined) agentButton.dataset.enabledTitle = agentButton.title;
    agentButton.disabled = gated;
    agentButton.title = gated
      ? `Agent mode needs a model, or the Needle extra, to call tools. ${AI_OFFLINE_HINT}.`
      : engine
        ? "Agent, app tools only. With no model, Agent answers with the app's own tools: the time, sums, counts, notes on a topic and acts. Needle picks a tool for the rest. A model does more."
        : agentButton.dataset.enabledTitle;
  }
  renderWebSearchToggle();
  const agent = $("tools-toggle").checked && !gated;
  if (!(agent && modelStatus?.model_ready !== true)) showAgentNoModelHint(false);
  // Two `addEventListener` calls for Quit and Clear-history used to sit here,
  // spliced into the middle of this function by an editing accident. It parsed,
  // so nothing complained: but this function runs on every chat-mode change,
  // so each call bound *another* listener to both buttons. Clicking Quit after
  // switching modes a few times opened that many confirm dialogs and fired
  // that many shutdown requests. The correctly-placed copies of both are
  // registered once, at the bottom of this file, where every other handler is.
  for (const button of document.querySelectorAll("#chat-mode-seg button")) {
    const active = button.dataset.chatMode === (agent ? "agent" : "chat");
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

//: Agent with no model (INBOX 840, CHAT_PLAN 22a): the first choice of it says
//: so under the composer; the segment's title always does.
function showAgentNoModelHint(on) {
  const line = $("chat-agent-hint");
  if (line) line.classList.toggle("hidden", !on);
}

async function setChatMode(mode) {
  const agent = mode === "agent";
  $("tools-toggle").checked = agent;
  if (agent && agentModeAvailable() && modelStatus?.model_ready !== true && !prefs.has("agentNoModelHint")) {
    prefs.set("agentNoModelHint", "1");
    showAgentNoModelHint(true);
  }
  renderChatModeSeg();
  // Remembered, because it is a way of working rather than a per-message
  // choice: the same preference the checkbox always wrote.
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ tools_enabled: agent }),
  }).catch(() => {});
}

function backendLabel(status) {
  return (status && status.provider) === "openai" ? "The model server" : "Ollama";
}

// True while the user is mid-edit, so a status poll doesn't overwrite the
// address they are halfway through typing. The polling that keeps this screen
// live is the reason: without it, a five-second refresh eats every third
// keystroke.
let backendFieldsDirty = false;


function renderSettings() {
  const status = modelStatus;
  const ollamaLine = $("ollama-status");

  //: **Only "can't reach" when it cannot** (INBOX 435): this said the
  //: app's server was unreachable while the app was plainly running, on a
  //: first open before the status had answered and whenever a slow model
  //: server ran the poll past its budget.
  if (!status) {
    ollamaLine.textContent =
      {
        slow: "The model server is slow to answer. Checking again…",
        error: "Couldn't read the models' status. Checking again…",
        down: "Can't reach the Tessellate server.",
      }[modelStatusProblem] || "Checking the models…";
    ollamaLine.className = `status ${modelStatusProblem === "down" ? "off" : "is-checking"}`;
    //: The pane's shape under the line while it waits, never the line alone
    //: (DESIGN.md's list recipe). Not when the answer is a fault: a skeleton
    //: says "on its way", and "can't reach" is not that.
    if (modelStatusProblem === "down") clearSkeletons($("models-skeleton"));
    else showSkeletons($("models-skeleton"), 2);
    if (!modelStatusProblem) refreshModelStatus().then(() => settingsOpen() && renderSettings());
    return;
  }
  clearSkeletons($("models-skeleton"));

  // Name the backend that actually answered. Saying "Ollama not detected"
  // when the app was pointed at LM Studio sends people to install the wrong
  // thing (§6).
  const backend = backendLabel(status);
  //: The dot is the line's class, as on the search engine line under it,
  //: not a typed "●"/"○" beside a CSS dot: two alphabets for one signal.
  //: Section 21 row 12: an address the person typed that nothing answers is
  //: a different problem from a server that is not started, and says so.
  ollamaLine.textContent = status.ollama_running
    ? `${backend} is running`
    : status.unreachable_hint || `${backend} isn't running`;
  ollamaLine.className = `status ${status.ollama_running ? "ok" : "off"}`;
  //: A slow poll keeps the last answer on screen (see refreshModelStatus), so
  //: the line says so instead of presenting a stale answer as fresh.
  if (modelStatusProblem === "slow") {
    ollamaLine.textContent = "The model server is slow to answer. Showing the last answer.";
    ollamaLine.className = "status is-checking";
  }
  renderBackendPicker(status);
  const embeddingError = $("embedding-error");
  embeddingError.classList.toggle("hidden", !status.embedding_error);
  //: A missing optional package arrives as a sentence the backend wrote for
  //: people ("Search by meaning is being installed..."), not an exception, so
  //: it is shown as it is with the one alternative that needs no install: an
  //: Ollama embedding model. Said even when Ollama is not running, because
  //: the owner's report was exactly that case ("no nomic-embed-text
  //: suggested") and the button below only exists while it is.
  //: The notice recipe's icon first (section 21 rows 1 and 2), then the line.
  const say = (text) => setLabel(embeddingError, `ph:warning ${text}`);
  if (status.embedding_error && /^Search by meaning/.test(status.embedding_error)) {
    say(
      `${status.embedding_error}. ` +
      (status.ollama_running
        ? `Or switch the search engine to ${EMBEDDING_FALLBACK_MODEL} below: smaller, and offline.`
        : `Or start Ollama and pick ${EMBEDDING_FALLBACK_MODEL} as the search engine: smaller, and offline.`)
    );
  } else if (status.embedding_error) {
    say(
      `Search engine problem: ${status.embedding_error}: semantic search is ` +
      "falling back to keywords. Quick fix: switch the search engine below to " +
      "an Ollama embedding model (download nomic-embed-text from the list), " +
      "it runs fully offline. Full details in Settings → Logs."
    );
  }
  // The one-click version of the "quick fix" sentence above: only offered
  // when it can actually be carried out (Ollama has to be running to either
  // pull or use an Ollama embedding model), and not while the fix is
  // already running or already switched over.
  const fixRow = $("embedding-error-fix-row");
  const alreadyOnOllama = status.embedding_backend === "ollama"
    && status.embedding_model === EMBEDDING_FALLBACK_MODEL;
  fixRow.classList.toggle(
    "hidden",
    !status.embedding_error
      || !status.ollama_running
      || !status.supports_pull
      || embeddingFallbackRunning
      || alreadyOnOllama
  );
  stagePrimary("embedding-apply", "embedding-error-fix", !fixRow.classList.contains("hidden"));
  renderSearchEngineHealth(status);
  // The "install Ollama" advice only helps someone who chose Ollama.
  $("ollama-help").classList.toggle(
    "hidden",
    status.ollama_running || status.provider !== "ollama"
  );
  $("models-config").classList.toggle("hidden", !status.ollama_running);
  // Downloads are an Ollama capability. Every other backend is handed a model
  // that is already on disk, so the panel hides rather than offering a button
  // that cannot work.
  $("suggested-box").classList.toggle(
    "hidden",
    !status.ollama_running || status.supports_pull === false
  );

  // The search engine is always adjustable: its recommended option is the
  // built-in one, which needs no Ollama. Only the Ollama half of it depends
  // on Ollama being up.
  renderEmbeddingPicker(status);
  //: Always, not only while a backend answers: the rows come from saved
  //: settings, and a person with the server down still needs to see and clear
  //: an override (WORLD_CLASS_PLAN 20, "Still open").
  renderFeatureModels(status);
  settingsReadouts.smallModel?.();
  if (status.ollama_running) {
    renderChatModelPicker(status);
    renderUtilityModelPicker(status);
    renderVisionModelPicker(status);
  renderOcrModelPicker(status);
    renderAutonomousModelPicker(status);
    //: Both live in the lazy `settingsUi` file: one check that it has loaded
    //: covers the two (it has whenever Settings is open, the only time this runs).
    if (typeof renderSuggested === "function") {
      renderInstalledModels(status);
      renderSuggested(status);
    }
    renderModelSpec(status.chat_model);
  } else {
    $("installed-box").classList.add("hidden");
    $("model-spec").classList.add("hidden");
    $("model-spec-health").classList.add("hidden");
  }
  renderReindex(status);
}

// GET /tasks, once per status poll, feeding everything that wants to know what
// is running: the status bar's job slot, the Background tasks panel when it is
// open, and the notifications centre.
//
// That last one was a real gap rather than a tidy-up. `renderTaskHistory`
// records a finished job into the centre "whether or not this screen is open, 
// which is the point of the centre", but the only thing that called it was
// `renderTasks`, and the only thing that called *that* was the panel being on
// screen. So a re-index that finished while you were anywhere else, which is
// most of them, since these jobs run for minutes, was recorded nowhere. It is
// polled from here now, so the record does not depend on being watched.
async function refreshBackgroundTasks() {
  // Before the unlock there is no token and this is a guaranteed 401 on every
  // poll: noise in the browser's network log and in the server's, where it
  // reads as an auth failure worth investigating.
  if (!authToken()) {
    backgroundTasks = [];
    return;
  }
  const body = await apiJson("/tasks", { silent: true }).catch(() => null);
  backgroundTasks = (body && body.tasks) || [];
  noticeTaskTransitions(backgroundTasks, (body && body.history) || []);
  const auto = backgroundTasks.find((t) => t.auto);
  if (auto || lazyModuleLoads.has("semanticNotice")) semanticInstallNotice(auto);
  renderStatusBar();
  // One fetch, not two: the panel renders from this payload rather than asking
  // again a few milliseconds later.
  //: While the panel's stream is open it paints the rows (ai-tools.js
  //: `followTaskLines`); the poll then only keeps the bar current.
  if (settingsModalOpen() && currentSettingsSection === "tasks") {
    if (!taskLineStream.controller) renderTasks(body);
  } else renderTaskHistory((body && body.history) || []);
}

// --- a background job starting and finishing, said out loud --------------------
//
// Half of this existed and half did not, which is why it read as broken rather
// than as missing: `renderTaskHistory` records every *finish* into the
// notifications centre, but a **start** was recorded nowhere, and neither end
// was ever said out loud. So kicking off a re-index or an extras install and
// then going back to writing gave you no sign anything was happening and no
// sign when it stopped, the only trace was a screen inside Settings and a
// centre you had to open.
//
// What this adds is the transitions: a job appearing in `GET /tasks` and a job
// disappearing from it.
//
// The rule that keeps it from becoming noise: **a toast only for a job whose
// start this session actually saw.** These jobs run for minutes and the app
// may well have been opened halfway through one; announcing the end of
// something you were never told had begun is a notification about nothing.
// The centre still records both ends either way, because that is a record
// rather than an interruption.

//: The jobs seen running on the previous poll, keyed the way `taskKey` keys
//: them. A Map rather than a Set so a finish can name the job that ended
//: without needing the poll it vanished from to still carry it.
const seenRunningTasks = new Map();

//: The activity panel's row for each of those jobs, keyed the same way. Kept
//: beside `seenRunningTasks` rather than inside it because the two answer
//: different questions: that map is "did this session see it start", which is
//: what decides whether its end is announced, and this one is "which row on
//: screen is it".
const backgroundRunRows = new Map();

function taskKey(task) {
  // `name` distinguishes two downloads running at once; `kind` alone would
  // merge them into one job that appears to start twice and finish once.
  return `${task.kind || "job"}:${task.name || ""}`;
}

//: **Housekeeping is listed, not announced** (INBOX 432). Warming the filing
//: model at launch opened the Agent activity panel over the notes and then
//: flew "Finished: Warming up the filing model" past the corner, two signals
//: for work nobody asked for and nothing waits on; filing a note already has
//: its own line under the composer. They still get a row in the run list and
//: still say so when they fail.
//: Start-up upkeep and Settings downloads too (INBOX 653).
const QUIET_TASK_KINDS = new Set([
  "job-warm-filing", "job-file-entry", "filing-late",
  "embeddings", "embedding-model", "reindex", "searxng-start", "searxng",
  "job-caption", "caption", "page-read", "pull", "extra",
]);

function noticeTaskTransitions(running, history) {
  const now = new Map(running.map((task) => [taskKey(task), task]));

  //: A running job's row keeps its fraction and its own status line up to
  //: date. It is the same run list the chat's skill runs land in, an
  //: autonomous pass rewriting tags in the background is exactly the "agent
  //: model activity" the report was about, and reading it off `/tasks` is how
  //: it gets a progress bar the chat runs cannot have.
  for (const [key, task] of now) {
    const run = backgroundRunRows.get(key);
    if (!run) continue;
    run.progress = typeof task.progress === "number" ? task.progress : null;
    run.detail = task.detail || "";
    renderAgentRunSummary(run);
  }

  for (const [key, task] of now) {
    if (seenRunningTasks.has(key)) continue;
    seenRunningTasks.set(key, task);
    //: A chat answer, a transcription: the person is watching it where they
    //: started it. The status bar and Running jobs list it; nothing announces it.
    if (task.watched) continue;
    const run = addAgentRun({
      kind: "job",
      name: task.label,
      icon: "ph:gear",
      detail: task.detail || "",
    });
    run.progress = typeof task.progress === "number" ? task.progress : null;
    renderAgentRunSummary(run);
    backgroundRunRows.set(key, run);
    if (!QUIET_TASK_KINDS.has(task.kind)) openPanelForRun(run);
    task.noticeId = recordNotification({
      kind: "task",
      title: `Started: ${task.label}`,
      detail: task.detail || "",
      runId: task.run_id || "",
      // Keyed per *start*, not per job. It used to be `task-start:${key}`,
      // which deduped against localStorage, so the second time the
      // autonomous pass (or any recurring job) ran, its start recorded
      // nothing at all, forever, because an entry with that exact id was
      // already stored from the first run days earlier. The poll-repeat this
      // was defending against is already handled by `seenRunningTasks` two
      // lines up, which `continue`s before reaching here.
      key: `task-start:${key}:${Date.now()}`,
    });
  }

  for (const [key, task] of [...seenRunningTasks]) {
    if (now.has(key)) continue;
    seenRunningTasks.delete(key);
    const row = backgroundRunRows.get(key);
    backgroundRunRows.delete(key);
    if (task.watched) continue;
    // The outcome comes from the server's own history, on this same payload, 
    // "it stopped appearing in the running list" is true of a job that died as
    // much as one that succeeded, and a cheerful toast over a failure is how
    // people learn to ignore toasts. Newest first, so `find` takes the ending
    // that just happened rather than a previous run of the same job.
    const ended =
      history.find((item) => task.run_id && item.run_id === task.run_id) ||
      history.find((item) => (item.kind || "job") === (task.kind || "job"));
    //: Its "Started:" row now says how it ended (INBOX 811 item 4).
    if (task.noticeId) {
      const endKey = ended ? `task:${ended.kind || ended.label}:${ended.at}` : `${task.noticeId}:end`;
      settleNotification(task.noticeId, { key: endKey, ...taskEndingWords(ended, task.label) });
    }
    if (ended && ended.outcome === "failed") {
      endAgentRun(row, { state: "failed" });
      agentActivityNotice(`Failed: ${ended.label || task.label}`, { isError: true });
    } else if (ended && ended.outcome === "cancelled") {
      endAgentRun(row, { state: "stalled", detail: "cancelled" });
      // Not an error and not an achievement, the user stopped it and already
      // knows. Recorded in the centre by renderTaskHistory; no toast.
      continue;
    } else {
      endAgentRun(row, { state: "done" });
      if (!QUIET_TASK_KINDS.has(task.kind)) agentActivityNotice(`Finished: ${(ended && ended.label) || task.label}`);
    }
  }
}

// --- optional extras and embedding models: Settings, Packages, is settings-packages.js (lazy, INBOX 595) ---

// --- The Local chip (row 1641, WORLD_CLASS_PLAN 22.1 item 9) -----------------
//: The privacy receipt's verdict for this launch (`GET /privacy/verdict`, the
//: receipt's own answer without its lists), as one word in the top bar and a
//: row of the phone's header menu. It asks again every five minutes, and
//: whenever Settings, Privacy has just read the full record.
const PRIVACY_CHIP_WORDS = {
  stayed_on_this_computer: ["shield-check", "Local", "Nothing left this computer since the app started."],
  local_network: ["wifi-high", "Local network", "Only devices on your own network were contacted since the app started."],
  internet: ["globe-hemisphere-west", "Online", "This app connected to the internet since it started."],
};
const PRIVACY_CHIP_MS = 5 * 60 * 1000;

function paintPrivacyChip(verdictKey) {
  const chip = $("privacy-chip");
  if (!chip) return;
  const [icon, word, sentence] = PRIVACY_CHIP_WORDS[verdictKey] || PRIVACY_CHIP_WORDS.stayed_on_this_computer;
  chip.classList.remove("hidden");
  chip.classList.toggle("is-online", verdictKey === "internet");
  chip.querySelector("i").className = `ph ph-${icon} ph-lead`;
  chip.querySelector(".privacy-chip-word").textContent = word;
  chip.title = `${sentence} Open the privacy record.`;
  chip.setAttribute("aria-label", `${word}: ${sentence} Open the privacy record`);
  //: The phone's header row reads these (phone-shell.js, `live` rows).
  chip.dataset.menuLabel = `ph:${icon} ${word}: privacy record`;
}

async function refreshPrivacyChip() {
  try {
    const body = await apiJson("/privacy/verdict", { silent: true });
    paintPrivacyChip(body?.verdict);
  } catch {
    //: No answer is no claim: the chip stays as it was (hidden before the
    //: first answer), never "Local" on a guess.
  }
}

function startPrivacyChip() {
  const chip = $("privacy-chip");
  if (!chip) return;
  refreshPrivacyChip();
  if (chip.dataset.wired) return;
  chip.dataset.wired = "1";
  chip.addEventListener("click", () => openSettingsModal("privacy"));
}

