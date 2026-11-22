// chat-groups.js: the chat list's Group by control and the group headings (L-world-class-180). Lazy: the boot scripts are at their gzip cap, so `loadConversationList` (sheets-selects.js) fetches this after it draws the rows (`lazyScript`) and hands it the list. The sort stays the `<select>` beside it; this adds the second choice, how the rows are cut into sections, kept in prefs.

(() => {
  //: What the choices are: the sort decides the order inside a section, this
  //: decides the sections. Pinned chats are always their own first section
  //: whenever any grouping is on (the list's older promise, kept).
  const MODES = [
    ["none", "No grouping", "The chats in one list"],
    ["day", "By day", "Today, yesterday, then each date"],
    ["month", "By month", "One section for each month"],
    ["size", "By length", "Long, medium and short chats"],
  ];

  const midnight = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();

  //: A row's section: its name and where it sorts (smaller is higher up).
  //: Counted in local calendar days, never 24-hour spans, as `chatTimeLabel` does.
  function sectionOf(row, mode, now) {
    if (row.classList.contains("pinned-conv")) return { name: "Pinned", rank: -1 };
    if (mode === "size") {
      const turns = Number(row.dataset.turns) || 0;
      return turns > 8 ? { name: "Long chats", rank: 0 } : turns > 2 ? { name: "Medium chats", rank: 1 } : { name: "Short chats", rank: 2 };
    }
    const then = parseServerTime(row.dataset.at) || now;
    if (mode === "month") {
      const back = (now.getFullYear() - then.getFullYear()) * 12 + now.getMonth() - then.getMonth();
      return { name: then.toLocaleDateString(undefined, { month: "long", year: "numeric" }), rank: back };
    }
    const days = Math.max(0, Math.round((midnight(now) - midnight(then)) / 86400000));
    if (days === 0) return { name: "Today", rank: 0 };
    if (days === 1) return { name: "Yesterday", rank: 1 };
    const sameYear = then.getFullYear() === now.getFullYear();
    return { name: then.toLocaleDateString(undefined, { weekday: days < 7 ? "long" : undefined, day: "numeric", month: "short", ...(sameYear ? {} : { year: "numeric" }) }), rank: days };
  }

  function groupMenu(mode, rebuild) {
    const items = MODES.map(([key, label, about]) =>
      makeMenuItem(`${label}${key === mode ? " ph:check" : ""}`, about, () => {
        prefs.set("chatSidebarGroup", key);
        rebuild();
        loadConversationList();
      })
    );
    const menu = kebabMenu(items, "Group your saved chats");
    menu.id = "chat-sidebar-group";
    const opener = menu.querySelector("button");
    setLabel(opener, "ph:rows");
    opener.title = "Group your saved chats";
    return menu;
  }

  //: Put the control in the head (once, and again when the choice changes so
  //: the tick moves), then cut the drawn rows into sections. Called after every
  //: draw of the list, so a grouping that is "none" costs a menu and no more.
  function chatGroups(list) {
    const mode = prefs.get("chatSidebarGroup", "none");
    const mount = () => {
      const head = document.querySelector("#chat-sidebar .sidebar-head-actions");
      if (!head) return;
      const fresh = groupMenu(prefs.get("chatSidebarGroup", "none"), mount);
      const old = document.getElementById("chat-sidebar-group");
      if (old) old.replaceWith(fresh);
      else head.prepend(fresh);
    };
    if (!document.getElementById("chat-sidebar-group")) mount();
    list.querySelectorAll(".conv-group-head").forEach((head) => head.remove());
    if (mode === "none" || !MODES.some(([key]) => key === mode)) return;
    lazyScript("/css/chat-groups-lazy.css");
    const rows = [...list.querySelectorAll(":scope > li:not(.conv-divider)")];
    if (!rows.length) return;
    list.querySelectorAll(":scope > .conv-divider").forEach((rule) => rule.remove());
    const now = new Date();
    //: A stable sort by section: inside one the order is the list's own (the sort's).
    const placed = rows.map((row, index) => ({ row, index, ...sectionOf(row, mode, now) }));
    placed.sort((a, b) => a.rank - b.rank || a.index - b.index);
    let last = null;
    for (const { row, name } of placed) {
      if (name !== last) {
        const head = document.createElement("li");
        head.className = "conv-group-head";
        head.setAttribute("role", "presentation");
        const title = document.createElement("h3");
        title.className = "conv-group-name";
        title.textContent = name;
        head.appendChild(title);
        list.appendChild(head);
        last = name;
      }
      list.appendChild(row);
    }
  }

  Object.assign(window, { chatGroups });
})();
