// chat-ghost.js: grey ghost-text completions in the chat box (CHAT_PLAN decision
// 69, L-chat-141). Lazy, loaded on the chat box's first focus (capture-ask.js).
// The search boxes already complete from the person's own words
// (search-suggest.js); this is the same idea for the one multi-line box, with
// no model and nothing fetched: the tags and titles of the notes the page holds
// and the searches recently run. Tab or Right at the end of a one-line draft
// takes it; typing on or Escape drops it. One switch for both: the Settings
// "Suggest as you type" preference (`searchSuggest`).
(() => {
  const CHAT_GHOST_MIN = 3;
  const chatGhost = { input: null, el: null, rest: "", measure: null, offered: 0, taken: 0 };

  //: Every candidate word or phrase, longest first is not needed: the first that
  //: continues the last word wins, tags before titles before searches.
  function chatGhostPool() {
    const entries = typeof allEntries !== "undefined" && Array.isArray(allEntries) ? allEntries : [];
    const tags = new Set();
    const titles = new Set();
    for (const entry of entries) {
      if (!entry || entry.is_private || entry.deleted_at || entry.archived_at) continue;
      for (const tag of entry.tags || []) tags.add(String(tag));
      if (entry.title) titles.add(String(entry.title).trim());
    }
    const recent = typeof searchRecent !== "undefined" ? searchRecent.load("notes") : [];
    return [...tags, ...titles, ...recent].filter(Boolean);
  }

  //: The rest of the word (or of the title) the draft ends in, "" when none. Only
  //: a one-line draft that ends in a letter is completed; a code fence or a
  //: password-shaped line never is.
  function chatGhostRest(text, pool) {
    if (!text || /\n/.test(text) || /`/.test(text) || !/[\p{L}\p{N}]$/u.test(text)) return "";
    const lower = text.toLowerCase();
    const word = /([\p{L}\p{N}'-]+)$/u.exec(lower)?.[1] || "";
    if (word.length < CHAT_GHOST_MIN) return "";
    //: The tails of the draft that start at a word, longest first, so a title of
    //: two words is continued from its first word.
    const tails = [...lower.matchAll(/(?<=^|\s)\S/g)].map((m) => lower.slice(m.index));
    for (const tail of tails) {
      const hit = pool.find((label) => label.length > tail.length && label.toLowerCase().startsWith(tail));
      if (hit) return hit.slice(tail.length);
    }
    return "";
  }

  function chatGhostHide() {
    chatGhost.rest = "";
    chatGhost.el?.classList.add("hidden");
  }

  function chatGhostPlace() {
    const { input, el } = chatGhost;
    if (!input || !el) return;
    const typed = input.value;
    const atEnd = input.selectionStart === typed.length && input.selectionEnd === typed.length;
    const enabled = prefs.get("searchSuggest", "on") !== "off";
    chatGhost.rest = enabled && atEnd && document.activeElement === input ? chatGhostRest(typed, chatGhostPool()) : "";
    if (!chatGhost.rest) return chatGhostHide();
    const style = getComputedStyle(input);
    chatGhost.measure = chatGhost.measure || document.createElement("canvas").getContext("2d");
    chatGhost.measure.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const rect = input.getBoundingClientRect();
    const left = rect.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft) + chatGhost.measure.measureText(typed).width - input.scrollLeft;
    const right = rect.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight);
    //: A draft that already wrapped has no single line to continue.
    if (left >= right - 4 || input.scrollHeight > input.clientHeight + 2) return chatGhostHide();
    el.textContent = chatGhost.rest;
    el.style.font = style.font;
    el.style.letterSpacing = style.letterSpacing;
    el.style.left = `${left}px`;
    el.style.top = `${rect.top + parseFloat(style.borderTopWidth) + parseFloat(style.paddingTop)}px`;
    el.style.maxWidth = `${right - left}px`;
    el.classList.remove("hidden");
    chatGhost.offered += 1;
  }

  function chatGhostAccept(event) {
    if (!chatGhost.rest) return;
    event.preventDefault();
    const input = chatGhost.input;
    input.value += chatGhost.rest;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    chatGhost.taken += 1;
    //: The accept rate is kept on this device only (decision 69's measure).
    prefs.set("chatGhostTally", JSON.stringify({ offered: chatGhost.offered, taken: chatGhost.taken }));
    chatGhostHide();
  }

  function openChatGhost(input) {
    if (chatGhost.input === input) return chatGhostPlace();
    chatGhost.input = input;
    chatGhost.el = document.createElement("span");
    chatGhost.el.className = "search-suggest-ghost chat-ghost hidden";
    chatGhost.el.setAttribute("aria-hidden", "true");
    document.body.append(chatGhost.el);
    input.addEventListener("input", chatGhostPlace);
    input.addEventListener("click", chatGhostPlace);
    input.addEventListener("blur", chatGhostHide);
    input.addEventListener("keydown", (event) => {
      if (event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "Tab" || event.key === "ArrowRight") chatGhostAccept(event);
      else if (event.key === "Escape" && chatGhost.rest) {
        event.stopPropagation();
        chatGhostHide();
      }
    }, true);
    chatGhostPlace();
  }

  //: No exports: the module opens itself on the box's focus (capture-ask.js only loads it).
  document.addEventListener("focusin", (event) => {
    if (event.target.id === "chat-input") openChatGhost(event.target);
  });
  if (document.activeElement?.id === "chat-input") openChatGhost(document.activeElement);
  if (typeof window.__chatGhostTest === "object") window.__chatGhostTest.rest = chatGhostRest;
})();
