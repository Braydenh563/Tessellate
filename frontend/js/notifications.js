// notifications.js: the bell's panel (WORLD_CLASS_PLAN 36E): drawing the
// rows, their read / unread / remove controls, and what a row's action does.
// Loaded on first use by `LAZY_MODULES.notifications` (app.js), whose
// stand-in for `openNotifications` fetches this file and calls the real one.
// The store, the badge, the toasts that record into it and `closeNotifications`
// stay in status.js: they run before the panel is ever opened.

//: Whether a kept action can still run from this session's closure.
function noticeLiveValid(live) {
  if (!live || (live.once && live.used)) return false;
  if (live.stacked) return undoStack.includes(live.stacked);
  return !live.until || Date.now() < live.until;
}

//: Where a stored `go` leads, found again by id when pressed: a target that
//: has gone since says so rather than opening an empty view.
const NOTICE_TARGETS = {
  entry: [(id) => apiJson(`/entries/${id}`, { silent: true }), (id) => flashEntry(id), "note"],
  conversation: [(id) => apiJson(`/conversations/${id}`, { silent: true }), (id) => { switchTab("chat"); return openConversation(id); }, "chat"],
  doc: [(id) => apiJson(`/documents/${id}`, { silent: true }), (id) => { switchTab("documents"); return openDocument(id); }, "document"],
  board: [(id) => apiJson("/whiteboard/boards", { silent: true }).then((all) => all.find((b) => b.id === id)), (id) => openWhiteboardBoard(id), "board"],
  reminder: [null, (id) => { editingReminderId = id; return flashReminder(id); }, "reminder"],
  capture: [null, () => startNewNote(), ""],
  //: A transcription that ended while nobody was looking (V1).
  recording: [(id) => apiJson(`/recordings/${id}`, { silent: true }), (id) => ensureModule("meetings").then(() => openRecordings(id)), "recording"],
};

async function runNotificationGo(action) {
  if (action.panel) return reopenAnswerPanel(action);
  if (action.settings) return openSettingsModal(action.settings, action.focus);
  if (action.exports) return openExportsFromNotification();
  if (action.filter) return showNotesFilter(action.filter);
  const target = NOTICE_TARGETS[action.open];
  if (target) {
    const found = target[0] ? await target[0](action.id).catch(() => null) : true;
    if (!found) return toast(`That ${target[2]} is no longer there.`);
    return target[1](action.id);
  }
  if (action.tab) return switchTab(action.tab);
}

function notificationGoes(action) {
  return Boolean(action && (action.tab || action.exports || action.panel || action.settings || NOTICE_TARGETS[action.open]));
}

//: The row's own action (INBOX 585), a quiet text button at the end of its
//: meta line (INBOX 811: a grey bordered block on a line of its own was
//: heavier than the message). Once a one-shot action is spent or out of
//: date there is nothing to press: the line says so in its own words ("Undo
//: expired", "Done"), never a disabled button beside the reason.
function notificationActionButton(item) {
  const action = item.action;
  if (!action || !(action.label || notificationGoes(action))) return null;
  const live = noticeLive.get(item.id);
  const label = action.label || (action.exports ? "Open folder" : action.filter ? "Show them" : "Open");
  if (!noticeLiveValid(live) && (action.once || !notificationGoes(action))) {
    const state = document.createElement("span");
    state.className = "notif-cta-state";
    state.textContent = live?.used || redoStack.includes(live?.stacked) ? "Done" : /^undo$/i.test(label) ? "Undo expired" : "Expired";
    return state;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost small quiet notif-cta";
  button.textContent = label;
  if (noticeLiveValid(live)) {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!noticeLiveValid(live)) return openNotifications({ keepWatermark: true });
      closeNotifications();
      //: The toast's own closure, which settles its stack entry itself
      //: (`settleUndoFromToast`), exactly as pressing the toast did.
      live.used = live.once;
      await live.run();
    });
  } else {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      closeNotifications();
      runNotificationGo(action);
    });
  }
  return button;
}

//: `keepWatermark`: a re-render from a row's own read/unread toggle must
//: not also stamp the "seen everything" watermark: that is what made one
//: tick mark every unread row as read (reported twice).
async function openNotifications({ keepWatermark = false } = {}) {
  const panel = $("notif-panel");
  const list = $("notif-list");
  panel.classList.remove("hidden");
  renderNotifMuteToggle();
  renderAgentActivityMode();

  // Fold in anything currently overdue on the server. This is what makes the
  // centre honest about time it was not running for: the event log can only
  // know what happened while a tab was open, and the reminders table knows
  // what is due regardless.
  const all = await apiJson("/reminders", { silent: true }).catch(() => null);
  for (const reminder of all || []) {
    if (reminder.done) continue;
    if (new Date(reminder.due_at).getTime() > Date.now()) continue;
    recordNotification({
      kind: "reminder",
      title: reminder.text,
      detail: `Due ${relativeTime(reminder.due_at)}`,
      key: reminderNoticeKey(reminder),
      action: { tab: "reminders" },
    });
  }

  const items = storedNotifications().slice().reverse();
  const readAt = notificationsReadAt();
  //: The count, beside the word it qualifies. The bell in the header already
  //: carries it, but the bell is what you clicked to get here, inside the
  //: panel the number has to say how many of the rows below are new.
  const forced = forcedUnreadIds();
  const chip = $("notif-unread");
  if (chip) {
    const unread = items.filter((item) => isNotificationUnread(item, readAt, forced)).length;
    chip.textContent = unread > 99 ? "99+" : String(unread);
    chip.classList.toggle("hidden", unread === 0);
    chip.title = `${unread} unread`;
  }
  list.replaceChildren();
  //: **An empty state, not a paragraph.** Reported with a screenshot: three
  //: lines of muted prose filled the panel where nothing had happened, which
  //: reads as an error message rather than as calm. The shape every other
  //: empty surface in this app uses, a glyph, a short line, and the
  //: explanation underneath in small text, says the same thing in a glance.
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "notif-empty";
    const glyph = document.createElement("span");
    glyph.className = "notif-empty-icon";
    setLabel(glyph, "ph:bell-simple");
    glyph.setAttribute("aria-hidden", "true");
    const headline = document.createElement("p");
    headline.className = "notif-empty-title";
    headline.textContent = "You're all caught up";
    const sub = document.createElement("p");
    sub.className = "muted text-sm notif-empty-sub";
    sub.textContent =
      "Reminders that come due, finished background jobs and runs that " +
      "stopped early collect here.";
    empty.append(glyph, headline, sub);
    list.appendChild(empty);
  }
  for (const item of items) {
    const row = document.createElement("li");
    row.className = "notif-row";
    const unread = isNotificationUnread(item, readAt, forced);
    if (unread) row.classList.add("notif-unread");

    //: **One row recipe** (INBOX 585, then 811): the icon column (the unread
    //: dot in its leading gutter, so a read row and an unread one put their
    //: icons on one edge), then one block: the message, its detail, and a
    //: meta line of the time and the row's action at the end; the row's two
    //: controls are the right-edge column, centred (INBOX 874).
    const dot = document.createElement("span");
    dot.className = "notif-dot";
    //: Named, not only drawn: a dot is a state shown by colour, so it says
    //: "Unread" to the pointer and to a screen reader (the owner's
    //: learnability rule, 2026-10-11).
    if (unread) {
      dot.setAttribute("role", "img");
      dot.setAttribute("aria-label", "Unread");
      dot.title = "Unread";
    } else dot.setAttribute("aria-hidden", "true");
    const icon = document.createElement("span");
    icon.className = "notif-icon";
    setLabel(icon, NOTIFICATION_ICONS[item.kind] || NOTIFICATION_ICONS.info);
    icon.setAttribute("aria-hidden", "true");

    const body = document.createElement("div");
    body.className = "notif-body";
    //: Title and time on one line, detail underneath. Reported with a
    //: screenshot: the time was glued to the end of a three-line detail
    //: and the title wrapped under a 2.25rem "mark read" button: the row
    //: read as a paragraph with a random button, not as a notification.
    const head = document.createElement("div");
    head.className = "notif-row-head";
    const title = document.createElement("span");
    title.className = "notif-title";
    setLabel(title, item.title);
    const time = document.createElement("time");
    time.className = "notif-time muted";
    time.dateTime = new Date(item.at).toISOString();
    time.textContent = relativeTime(time.dateTime);
    time.title = whenText(item.at);
    head.append(title);
    body.append(head);
    if (item.detail) {
      const meta = document.createElement("div");
      meta.className = "notif-meta muted";
      meta.textContent = item.detail;
      body.append(meta);
    }
    const foot = document.createElement("div");
    foot.className = "notif-foot";
    body.append(foot);
    row.append(dot, icon, body);

    //: The dot is the control. A row is either new or it is not, so this is a
    //: two-state toggle rather than a menu, and it sits where the "new"
    //: marker already is, so pressing the thing that says "unread" is what
    //: changes whether it is unread. `stopPropagation` because the row itself
    //: may navigate somewhere, and "keep this for later" is the opposite of
    //: "take me there now".
    const readToggle = document.createElement("button");
    readToggle.type = "button";
    readToggle.className = "ghost small icon-only notif-read-toggle";
    readToggle.setAttribute("aria-pressed", String(unread));
    readToggle.title = unread ? "Mark as read" : "Mark as unread";
    readToggle.setAttribute("aria-label", readToggle.title);
    setLabel(readToggle, unread ? "ph:circle" : "ph:check-circle");
    readToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      // Reported: "the individual mark as complete buttons don't work". A
      // row from before ids were stamped has no `item.id`, so the override
      // set had nothing to add and the click changed nothing visible. Stamp
      // one from its timestamp, stable across renders, unique enough.
      if (item.id == null) {
        item.id = `n-${item.at}`;
        const all = storedNotifications();
        const same = all.find((entry) => entry.at === item.at && entry.id == null);
        if (same) { same.id = item.id; prefs.set(NOTIFICATIONS_KEY, JSON.stringify(all)); }
      }
      setNotificationUnread(item.id, !unread);
      openNotifications({ keepWatermark: true });
    });
    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.className = "ghost small icon-only notif-dismiss";
    dismiss.title = "Remove this notification";
    dismiss.setAttribute("aria-label", `Remove: ${item.title}`);
    setLabel(dismiss, "ph:x");
    dismiss.addEventListener("click", (event) => {
      event.stopPropagation();
      // Focus goes to the next row's remove button, or the list, so a
      // keyboard run through the list does not drop back to the page.
      const next = row.nextElementSibling || row.previousElementSibling;
      dismissNotification(item);
      openNotifications({ keepWatermark: true }).then(() => {
        const index = next ? [...list.children].findIndex((li) => li.dataset.at === next.dataset.at) : -1;
        (list.children[index]?.querySelector(".notif-dismiss") || $("notif-close"))?.focus();
      });
    });
    const actions = document.createElement("span");
    actions.className = "notif-row-actions";
    actions.append(readToggle, dismiss);
    foot.append(time);
    const cta = notificationActionButton(item);
    if (cta) foot.append(cta);
    //: The third column of the row, centred on it (INBOX 874): not on the
    //: meta line, where a two-line row put them at its bottom.
    row.append(actions);
    row.dataset.at = String(item.at);

    // A notification you cannot act on is a notification you learn to ignore.
    // The whole row goes where its target is; a one-shot action (an Undo) is
    // only ever its own button.
    if (item.action && !item.action.once && notificationGoes(item.action)) {
      row.classList.add("notif-actionable");
      row.tabIndex = 0;
      row.title = item.action.exports ? "Open the exports folder" : "Open";
      const go = () => {
        closeNotifications();
        runNotificationGo(item.action);
      };
      row.addEventListener("click", go);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          go();
        }
      });
    }
    list.appendChild(row);
  }

  //: **The first steps, pinned first while one is left** (INBOX 904 B01): the
  //: card on the dashboard goes away with the first note or Hide, and a
  //: popup closed by accident had no way back. Drawn after the panel is up,
  //: since it asks three routes for its ticks.
  lazyScript("/js/first-run.js").then(async (ok) => {
    if (!ok || typeof firstStepsBellRow !== "function") return;
    const start = await firstStepsBellRow().catch(() => null);
    if (!start || list.querySelector(".notif-start")) return;
    list.prepend(start);
    list.querySelector(".notif-empty")?.remove();
  });

  // Opening the panel *is* reading them. Marked after rendering, so the
  // unread ones are still highlighted in the list you are looking at.
  //
  // The overrides survive it: a row deliberately kept unread must not be
  // cleared by looking at the panel, or "mark as unread" would last exactly
  // until the next time the bell is opened, which is no time at all.
  // The watermark moves on *close*, not on open (see closeNotifications):
  // while the panel is up, an unread row stays unread, so ticking one row
  // changes one row. Opening used to stamp it, and the next re-render, 
  // the one a tick causes, then showed every row as read (reported twice
  // as "mark one, all get marked").
  renderNotificationBadge();
}

function setNotificationUnread(id, unread) {
  const unreadIds = forcedUnreadIds();
  const readIds = forcedReadIds();
  if (unread) { unreadIds.add(id); readIds.delete(id); }
  else { unreadIds.delete(id); readIds.add(id); }
  setForcedUnreadIds(unreadIds);
  setForcedReadIds(readIds);
  renderNotificationBadge();
}

function dismissNotification(item) {
  const all = storedNotifications().filter((n) =>
    item.id != null ? n.id !== item.id : n.at !== item.at
  );
  try {
    prefs.set(NOTIFICATIONS_KEY, JSON.stringify(all));
    if (item.id != null && /^reminder:/.test(String(item.id))) {
      const gone = [...dismissedNotificationIds(), item.id].slice(-300);
      prefs.set(NOTIFICATIONS_DISMISSED_KEY, JSON.stringify(gone));
    }
  } catch {
    // Storage refused: the row stays, which is what the list shows next.
  }
  renderNotificationBadge();
}

//: **Where an export lands, from a notification.** On the desktop the OS file
//: manager opens on the folder; a browser tab has no file manager to hand
//: this to, so it gets the Settings list below, where every export has a
//: download link of its own.
async function openExportsFromNotification() {
  if (await desktopShell()) {
    apiJson("/files/open-exports-folder", { method: "POST" }).catch((error) => {
      toast(error.message || "Couldn't open the exports folder.", true);
    });
    return;
  }
  openSettingsModal("data", "exports-recent");
}
