// chat-order.js: how the sidebar lists saved chats (L-world-class-180). Lazy, fetched by the
// first `loadConversationList`: the sort, the grouping, and the one menu that changes them.
//
// The view (sort, group, pinned first) is kept by the server (`GET/PUT /conversations/view`,
// `core/chat_view.py`), so this menu, a typed "sort my chats by name" and the agent's
// `edit_chats` tool all change the same thing. Chats are grouped on the client from the
// summaries the list already holds: a chat carries `folder`, `last_at`, `pinned`.

(() => {
  lazyScript("/css/chat-order-lazy.css");

  const CHAT_SORTS = [
    ["recent", "ph:clock Recent", "Latest chat first"],
    ["oldest", "ph:clock-counter-clockwise Oldest", "Oldest chat first"],
    ["name", "ph:text-aa Name", "A to Z"],
    ["messages", "ph:chats Most messages", "Longest conversations first"],
  ];
  const CHAT_GROUPS = [
    ["none", "ph:rows No grouping", "One list"],
    ["day", "ph:calendar-blank By day", "Today, yesterday, then each day"],
    ["week", "ph:calendar By week", "This week, last week, then each week"],
    ["folder", "ph:folder By folder", "The folder each chat was filed in"],
  ];

  let chatView = { sort: "recent", group: "none", pinned: true };

  //: The stored view, read once per list load; an unreachable server keeps the one in hand.
  async function chatViewLoad() {
    try {
      chatView = { ...chatView, ...(await apiJson("/conversations/view")) };
    } catch {
      /* the last view stands */
    }
    return chatView;
  }

  //: Eight rows fit beside a conversation; grouped, a heading is worth a few more.
  function chatListLimit(searching) {
    return (searching ? 4 : chatView.group === "none" ? 1 : 3) * RECENT_CHATS_SHOWN;
  }

  // Pinned notes stay first by default (a divider marks the boundary), that promise predates this
  // control; only the order *within* each of the two groups changes. `pinnedFirst` false lets a
  // pinned chat sort among the rest.
  function sortConversations(conversations, mode, limit = Infinity, pinnedFirst = true) {
    const pinned = pinnedFirst ? conversations.filter((c) => c.pinned) : [];
    const rest = pinnedFirst ? conversations.filter((c) => !c.pinned) : [...conversations];
    const when = (c) => new Date(c.updated_at);
    const byMode = {
      recent: (a, b) => when(b) - when(a),
      oldest: (a, b) => when(a) - when(b),
      messages: (a, b) => (b.turns || 0) - (a.turns || 0) || when(b) - when(a),
      name: (a, b) => a.title.localeCompare(b.title),
    }[mode] || null; // "recent" is already the server's own order
    if (byMode) {
      pinned.sort(byMode);
      rest.sort(byMode);
    }
    //: The rows the switcher draws (audit 1028 E46): more than five pinned chats
    //: used to fill all eight rows and push every recent chat out, so the newest
    //: three always keep a place; the other pinned ones are in the Library.
    const pinnedShown = pinned.slice(0, Math.max(limit - Math.min(rest.length, 3), 0));
    return [...pinnedShown, ...rest.slice(0, Math.max(limit - pinnedShown.length, 0))];
  }

  //: Monday of the week `date` is in, at midnight (the day-and-week labels count from it).
  function chatWeekStart(date) {
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    return start;
  }

  //: [sortKey, heading] of the group a chat falls in. The key orders the groups: newest first
  //: for a day or a week, A to Z for folders with the unfiled ones last.
  function chatGroupOf(chat, group, now = new Date()) {
    if (group === "folder") return chat.folder ? [chat.folder.toLowerCase(), chat.folder] : ["￿", "No folder"];
    const at = parseServerTime(chat.last_at) || new Date(chat.updated_at);
    const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    if (group === "day") {
      const days = Math.round((midnight(now) - midnight(at)) / 86400000);
      const heading = days <= 0 ? "Today" : days === 1 ? "Yesterday" : days < 7 ? at.toLocaleDateString(undefined, { weekday: "long" }) : at.toLocaleDateString(undefined, { day: "numeric", month: "short" });
      return [midnight(at).getTime(), heading];
    }
    const weeks = Math.round((chatWeekStart(now) - chatWeekStart(at)) / (7 * 86400000));
    const heading = weeks <= 0 ? "This week" : weeks === 1 ? "Last week" : `Week of ${chatWeekStart(at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
    return [chatWeekStart(at).getTime(), heading];
  }

  //: The list as the sidebar draws it: sorted, and with `{ heading }` rows between its groups.
  //: With pinned chats first they are the first group, "Pinned", whatever the grouping.
  function chatListRows(conversations, view = chatView, limit = Infinity) {
    const sorted = sortConversations(conversations, view.sort, limit, view.pinned);
    if (view.group === "none") return sorted;
    const lead = view.pinned ? sorted.filter((c) => c.pinned) : [];
    const buckets = new Map();
    for (const chat of view.pinned ? sorted.filter((c) => !c.pinned) : sorted) {
      const [key, heading] = chatGroupOf(chat, view.group);
      if (!buckets.has(heading)) buckets.set(heading, { key, rows: [] });
      buckets.get(heading).rows.push(chat);
    }
    const order = [...buckets.entries()].sort(([, a], [, b]) => (view.group === "folder" ? String(a.key).localeCompare(String(b.key)) : view.sort === "oldest" ? a.key - b.key : b.key - a.key));
    return [...(lead.length ? [{ heading: "Pinned" }, ...lead] : []), ...order.flatMap(([heading, { rows }]) => [{ heading }, ...rows])];
  }

  //: A group's heading row: a list item, not a button, named for a screen reader as the list's own.
  function chatGroupRow(heading) {
    const li = document.createElement("li");
    li.className = "conv-group";
    li.setAttribute("role", "presentation");
    li.textContent = heading;
    return li;
  }

  //: The view as it was is the Undo (`offerUndo`), and the redo puts the new one back.
  async function chatViewChange(change) {
    const before = { sort: chatView.sort, group: chatView.group, pinned: chatView.pinned };
    const put = async (view) => {
      chatView = { ...chatView, ...(await apiJson("/conversations/view", { method: "PUT", body: JSON.stringify(view) })) };
      chatViewMount();
      loadConversationList();
    };
    await put(change);
    const after = { sort: chatView.sort, group: chatView.group, pinned: chatView.pinned };
    offerUndo("Changed how chats are listed", "Chat list changed.", () => put(before), () => put(after));
  }

  //: The sort-and-group menu in the sidebar's head: one `kebabMenu` of choices, the chosen rows marked.
  function chatViewMount() {
    const slot = $("chat-sidebar-view");
    if (!slot) return;
    const row = ([value, label, title], key, group) => ({ label, title, group, current: chatView[key] === value, run: () => chatViewChange({ [key]: value }) });
    const items = [
      ...CHAT_SORTS.map((s) => row(s, "sort", "sort")),
      ...CHAT_GROUPS.map((g) => row(g, "group", "group")),
      { label: "ph:push-pin Pinned first", title: "Keep pinned chats above the rest", group: "pin", current: chatView.pinned, run: () => chatViewChange({ pinned: !chatView.pinned }) },
    ];
    const menu = kebabMenu(items, "Sort and group chats");
    const opener = menu.querySelector(".kebab-opener");
    setLabel(opener, "ph:sort-descending");
    opener.title = "Sort and group your saved chats";
    slot.replaceChildren(menu);
  }

  //: Filing a chat: the folders already in use, "No folder", and what is typed as a new one, in the app's picker. Undo files it back where it was.
  async function chatMoveToFolder(conversation) {
    //: A failed read says so: an empty list would offer "No folders yet" over folders that exist.
    let all;
    try {
      all = await apiJson("/conversations");
    } catch (error) {
      return toast(voiceLine("failed", "read your folders", error.message), true);
    }
    const used = [...new Set(all.map((c) => c.folder).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    const chosen = await new Promise((resolve) => {
      const shell = pickerDialog({ title: "Move to folder", placeholder: "Find a folder or type a new one…", searchLabel: "Find a folder or type a new one" });
      const box = pickerListbox(shell, "Folders");
      const paint = () => {
        const text = shell.search.value.trim().slice(0, 60);
        const needle = text.toLowerCase();
        const items = used.filter((f) => !needle || f.toLowerCase().includes(needle)).map((f) => ({ icon: "ph:folder", label: f, about: f === conversation.folder ? "Where it is now" : "", value: { folder: f } }));
        if (!needle && conversation.folder) items.push({ icon: "ph:folder-dashed", label: "No folder", about: "Take it out of its folder", value: { folder: "" } });
        if (text && !used.some((f) => f.toLowerCase() === needle)) items.unshift({ icon: "ph:folder-plus", label: `New folder “${text}”`, about: "", value: { folder: text } });
        box.fill(items, needle, { icon: "ph:folder", title: "No folders yet", text: "Type a name to make the first one." });
      };
      shell.search.addEventListener("input", paint);
      paint();
      shell.open(resolve);
    });
    if (!chosen || chosen.folder === (conversation.folder || "")) return;
    chatWriteRecord("chatFolderUndo", conversation.id, conversation.folder || "", chosen.folder);
    await apiJson(`/conversations/${conversation.id}/folder`, { method: "PUT", body: JSON.stringify({ folder: chosen.folder }) });
    loadConversationList();
  }

  //: The file's whole surface: what the sidebar's list load calls.
  window.ChatOrder = { load: chatViewLoad, limit: chatListLimit, rows: chatListRows, groupRow: chatGroupRow, mount: chatViewMount, move: chatMoveToFolder };
})();
