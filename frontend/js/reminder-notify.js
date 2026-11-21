// A due reminder's system notification (TIMELINE_PLAN 11 row 4, WORLD_CLASS_PLAN
// decision 69). Loaded by `checkDueReminders` (status.js) the first time
// something comes due, so none of it is boot code.
//
// With no push server nothing can wake the service worker at a time, so the
// page's own timer is what fires: it runs in a hidden tab and in an installed
// app's window. What the worker adds is a notification that outlives the
// tab and carries Done and Snooze 10 minutes (`notificationclick`, sw.js).
// In the desktop app the launcher posts the system notification itself
// (`/health`'s `os_notify`, core/reminder_notifier.py), so the page posts
// none and keeps the toast, the chime and the centre.

(() => {
  const reminderNotify = { launcher: null, listening: false };

  async function launcherNotifies() {
    if (reminderNotify.launcher === null) {
      const health = await apiJson("/health", { silent: true }).catch(() => null);
      reminderNotify.launcher = Boolean(health && health.os_notify);
    }
    return reminderNotify.launcher;
  }

  //: The worker did Done or Snooze, or was asked to open the reminders; this
  //: page shows it now rather than at the next minute's poll.
  function listenToReminderWorker() {
    if (reminderNotify.listening || !navigator.serviceWorker) return;
    reminderNotify.listening = true;
    navigator.serviceWorker.addEventListener("message", (event) => {
      const kind = event.data && event.data.type;
      if (kind === "reminders-changed") loadReminders().catch(() => {});
      if (kind === "reminders-open") switchTab("reminders");
    });
  }

  async function showReminderNotification(title, body, reminderId) {
    if (await launcherNotifies()) return true;
    if (!("Notification" in window) || Notification.permission !== "granted") return false;
    const registration = await navigator.serviceWorker?.getRegistration?.().catch(() => null);
    if (!registration || !registration.showNotification) return notify(title, body);
    listenToReminderWorker();
    const tag = reminderId ? `reminder-${reminderId}` : "memorymap-reminders";
    //: **A token for this reminder alone, never the session's.** Whatever is in a
    //: notification's data sits in the browser's notification store, so the
    //: worker's Done and Snooze carry a token the server minted for this
    //: reminder and those two actions, good for a day (`core/reminder_token.py`).
    //: Without one (the server did not answer) the notification has no buttons.
    const scoped = reminderId
      ? await apiJson(`/reminders/${reminderId}/notification-token`, { method: "POST", silent: true }).catch((error) => {
          //: No token: the notification still shows, without Done and Snooze.
          console.warn("reminder notification without its buttons", error);
          return null;
        })
      : null;
    try {
      await registration.showNotification(title, {
        body,
        icon: "/icon-512.png",
        tag,
        //: The worker acts with this after the tab is gone: the scoped token
        //: and the person's offset, for a repeat's next day.
        data: { id: reminderId || null, token: scoped?.token || null, tz: -new Date().getTimezoneOffset() },
        actions: scoped?.token
          ? [
              { action: "done", title: "Done" },
              { action: "snooze", title: "Snooze 10 minutes" },
            ]
          : [],
      });
    } catch {
      return notify(title, body);
    }
    //: Closed after the same 12 s as a page notification (status.js): the owner
    //: reported ones that stayed until closed by hand.
    setTimeout(() => {
      registration
        .getNotifications({ tag })
        .then((shown) => shown.forEach((n) => n.close()))
        .catch(() => {});
    }, NOTIFICATION_AUTOCLOSE_MS);
    return true;
  }

  //: One notification for one reminder, a summary for several; the toast
  //: always, because Do Not Disturb can hide the system one without the app
  //: knowing. An early alert has no Done: it is not due yet.
  async function announceReminders(fresh) {
    const one = fresh.length === 1 ? fresh[0] : null;
    const text = one ? one.text : `${fresh.length} reminders are due`;
    //: Why it matters, from what it is about (CHAT_PLAN section 1 row 6): a
    //: reminder made from a note or a document says so under its words.
    const about = one && one.target_title ? `\nAbout ${toastName(one.target_title)}` : "";
    await showReminderNotification(one ? "Reminder" : "Tessellate", text + about, one && !one.early ? one.id : null);
    const brief = one ? await apiJson(`/reminders/${one.id}/brief`, { silent: true }).catch(() => null) : null;
    const notes = brief?.notes || [];
    if (!notes.length) return toast(text, false, { exempt: true });
    //: A meeting-prep brief (L-general-11): the last notes the reminder's
    //: words point at, so "Meet Priya" opens with what was written last time.
    const open = (note) => ({ label: `Open ${toastName(note.title)}`, run: () => openNoteEditor(note.id) });
    const [first, second] = notes.map(open);
    toastAction(`${text}\nLast notes: ${notes.map((n) => toastName(n.title)).join(", ")}`, first.label, first.run, {
      ms: 15000,
      ...(second ? { also: second } : {}),
    });
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { announceReminders });
})();
