// chat-time.js: the time on each chat message (INBOX 868, Brief 103). Lazy:
// the boot scripts are at their gzip cap, so chat-agent.js fetches this on the
// first bubble (`lazyScript`) and openConversation hands it the saved
// messages. Not a `LAZY_MODULES` bundle, because app.js is at its own cap.

//: **How a message time reads**, by how far back it is, in the viewer's
//: locale (Intl, never a hand-built "14:05"): today the clock time,
//: "Yesterday 14:05", within the last week the weekday and time, older the
//: date (with the year once it is another year). `title` is the whole date
//: and time, for the hover. The calendar days are counted in local midnights,
//: not 24-hour spans, so 23:50 last night is "Yesterday" at 00:10.
function chatTimeLabel(iso, now = new Date()) {
  const then = parseServerTime(iso);
  if (!then) return null;
  const clock = then.toLocaleTimeString(undefined, { timeStyle: "short", ...clockOptions() });
  const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((midnight(now) - midnight(then)) / 86400000);
  let text;
  if (days <= 0) text = clock;
  else if (days === 1) {
    const word = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(-1, "day");
    text = `${word.charAt(0).toLocaleUpperCase()}${word.slice(1)} ${clock}`;
  } else if (days < 7) text = `${then.toLocaleDateString(undefined, { weekday: "short" })} ${clock}`;
  else {
    const sameYear = then.getFullYear() === now.getFullYear();
    text = then.toLocaleDateString(undefined, { day: "numeric", month: "short", ...(sameYear ? {} : { year: "numeric" }) });
  }
  return { text, title: then.toLocaleString(undefined, { dateStyle: "full", timeStyle: "medium", ...clockOptions() }), iso: then.toISOString() };
}

//: Put (or take away) one bubble's time. It lives in the bubble's meta row
//: (the cost line under an answer) when there is one, so the two read as one
//: line; a bubble with no meta row gets a row of just the time. Idempotent:
//: the reopen pass and the live observer may both reach the same bubble.
function paintChatTime(bubble, iso) {
  const label = iso ? chatTimeLabel(iso) : null;
  let stamp = bubble.querySelector(":scope > .msg-meta > .msg-meta-when, :scope > .answer-foot-bar > .msg-meta > .msg-meta-when, :scope > .msg-meta-when");
  if (!label) {
    const row = stamp?.parentElement;
    stamp?.remove();
    if (row && row.classList.contains("msg-meta-solo")) row.remove();
    return;
  }
  if (!stamp) {
    stamp = document.createElement("time");
    stamp.className = "msg-meta-item msg-meta-when";
  }
  stamp.textContent = label.text;
  stamp.title = label.title;
  stamp.dateTime = label.iso;
  placeChatTime(bubble, stamp);
}

//: The cost row may already sit in the answer's foot bar (it moves there the
//: moment it lands), so a reopened chat, whose time arrives after the lazy
//: script, must look there too: with only direct children counted it found
//: no row, made a solo one, and the foot bar kept that and dropped the cost
//: line (INBOX 1693 b: "reloaded, only the text and the time").
function placeChatTime(bubble, stamp) {
  const rows = bubble.querySelectorAll(":scope > .msg-meta:not(.msg-meta-solo), :scope > .answer-foot-bar > .msg-meta:not(.msg-meta-solo)");
  const row = rows[rows.length - 1];
  const solo = bubble.querySelector(":scope > .msg-meta-solo");
  if (row) {
    row.appendChild(stamp);
    if (solo && !solo.children.length) solo.remove();
    return;
  }
  if (stamp.parentElement?.parentElement === bubble) return;
  const own = solo || document.createElement("div");
  own.className = "msg-meta msg-meta-solo muted";
  own.appendChild(stamp);
  if (!own.parentElement) {
    // Above the hover actions, which are positioned off the bubble's bottom.
    bubble.insertBefore(own, bubble.querySelector(":scope > .msg-actions"));
  }
}

//: A reopened chat: the messages the server sent, in order, one bubble each.
//: A message saved before stamps existed has no `at` and shows no time rather
//: than a wrong one (the chat's own time would read as the time of every
//: line). Bubbles past the saved messages are a turn still streaming; the
//: live observer below already stamped those.
function stampChatTimes(messages) {
  const bubbles = document.querySelectorAll("#chat-messages > .msg.user, #chat-messages > .msg.assistant");
  messages.forEach((message, i) => {
    const bubble = bubbles[i];
    if (!bubble || !bubble.classList.contains(message.role)) return;
    bubble.dataset.at = message.at || "";
    paintChatTime(bubble, message.at);
  });
}

//: The live side: a bubble that appears gets the time it appeared. A question
//: is stamped at once; an answer's time is held until its meta row (cost line)
//: lands, which the same observer waits for, so a stamp never sits under a
//: half-streamed answer. One MutationObserver, on direct children only (the
//: pane's bubbles, an answer's rows): the streaming text changes deeper down
//: and never wakes it.
const chatTimePane = document.getElementById("chat-messages");
const chatTimeWatch = new MutationObserver((records) => {
  for (const record of records) {
    if (record.target === chatTimePane) {
      record.addedNodes.forEach(adoptChatBubble);
      continue;
    }
    const bubble = record.target;
    if (bubble.dataset.at && bubble.querySelector(":scope > .msg-meta:not(.msg-meta-solo)")) {
      paintChatTime(bubble, bubble.dataset.at);
    }
  }
});

function adoptChatBubble(bubble) {
  if (!bubble.matches?.(".msg.user, .msg.assistant") || bubble.dataset.at !== undefined) return;
  bubble.dataset.at = new Date().toISOString();
  if (bubble.classList.contains("user")) paintChatTime(bubble, bubble.dataset.at);
  else chatTimeWatch.observe(bubble, { childList: true });
}

if (chatTimePane) {
  chatTimeWatch.observe(chatTimePane, { childList: true });
  chatTimePane.querySelectorAll(":scope > .msg").forEach(adoptChatBubble);
}
