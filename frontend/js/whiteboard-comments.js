(() => {
  // whiteboard-comments.js: comments threads, item links and their marks on the board (decision 17).
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: --- Comments (WHITEBOARD_PLAN decision 17) --------------------------------
  //:
  //: A thread per item, in the item's own data (a card's `comments` column), so
  //: it moves, copies, undoes and goes with its item. A count mark at the top
  //: right of every commented item, in one layer for all three kinds; the mark,
  //: the item menu and a topic's menu open the thread in the help popover's
  //: shell. A connector takes none (`wbSketchParsedData` is null for a link).

  const WB_COMMENTS_MAX = 100;

  function wbTakesComments(kind, item) {
    if (!item) return false;
    return kind === "sketch" ? Boolean(wbSketchParsedData(item)) : kind === "node" || kind === "object";
  }

  function wbItemComments(kind, item) {
    if (!item) return [];
    const list = kind === "node" ? item.comments : kind === "object" ? item.data?.comments : wbSketchParsedData(item)?.comments;
    return Array.isArray(list) ? list : [];
  }

  function wbFindItem(kind, id) {
    return (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id) || null;
  }

  //: One undo step: the item's whole state before, the lock's "move" entry.
  async function wbSetComments(kind, item, list) {
    const next = list.length ? list : null;
    wbPushUndo({ action: "move", kind, id: item.id, before: WB_KIND_INFO[kind].payload(item) });
    if (kind === "node") {
      item.comments = next;
      await wbSaveNode(item);
    } else if (kind === "object") {
      const data = { ...item.data };
      if (next) data.comments = next;
      else delete data.comments;
      item.data = data;
      await wbSaveObject(item);
    } else {
      await wbSaveSketchProps(item, { comments: next || undefined });
    }
    wbPaintCommentMarks();
  }

  //: **A shape's own link** (draw.io Edit link): a web page (http or https) or
  //: a view of this app (a note's `#/notes/12`, or any pasted app link),
  //: stored as `link` in a shape's or a text box's data and opened from the
  //: mark on its top-left corner. A note card is a note already, so it has none.
  function wbTakesLink(kind, item) {
    if (!item || kind === "node") return false;
    if (kind === "sketch") return Boolean(wbSketchParsedData(item));
    return !WB_MAP_KINDS.has(item.kind);
  }

  function wbItemLink(kind, item) {
    if (!wbTakesLink(kind, item)) return "";
    const link = kind === "sketch" ? wbSketchParsedData(item)?.link : item.data?.link;
    return typeof link === "string" && (/^https?:\/\//i.test(link) || routeEntry(link) || wbFmtState.drawMore?.frameOf(link)) ? link : "";
  }

  //: What a typed or pasted address becomes: an app link's hash, a web
  //: address (https:// added to a bare one), or "" for anything else.
  function wbLinkFromText(text) {
    const value = String(text || "").trim();
    const hash = appAddressHash(value) || (routeEntry(value) ? value : "");
    if (hash) return hash;
    if (/^https?:\/\/[^\s]+$/i.test(value)) return value;
    return /^[\w-]+(\.[\w-]+)+(\/\S*)?$/.test(value) ? "https://" + value : "";
  }

  async function wbSetItemLink(kind, item, link) {
    wbPushUndo({ action: "move", kind, id: item.id, before: WB_KIND_INFO[kind].payload(item) });
    if (kind === "sketch") {
      await wbSaveSketchProps(item, { link: link || undefined });
    } else {
      const data = { ...item.data };
      if (link) data.link = link;
      else delete data.link;
      item.data = data;
      await wbSaveObject(item);
    }
    wbPaintCommentMarks();
  }

  function wbOpenItemLink(link) {
    const page = wbFmtState.drawMore?.frameOf(link);
    if (page) wbPageGo(page.id);
    else if (link.startsWith("#/")) location.hash = link;
    else window.open(link, "_blank", "noopener,noreferrer");
  }

  //: Link…: a note from the notebook's own picker, or an address typed or
  //: pasted; with a link already set, open it or take it off.
  function wbEditItemLink() {
    const kind = wbSelectedItem?.kind, item = kind ? wbFindItem(kind, wbSelectedItem.id) : null;
    if (!wbTakesLink(kind, item)) return;
    const now = wbItemLink(kind, item);
    const items = [
      makeMenuItem("ph:note A note…", "Link this to one of your notes", async () => {
        const entry = await pickEntryDialog("Link to a note");
        if (entry) await wbSetItemLink(kind, item, routeHashFor("note", entry.id));
      }),
      makeMenuItem("ph:globe A web page or app link…", "Type or paste a web address, or an app link from Copy app link", async () => {
        const typed = await promptDialog("Link to a web page or app link", now.startsWith("#/") ? "" : now);
        if (typed === null || typed === undefined) return;
        const link = wbLinkFromText(typed);
        if (!link) {
          toast("That is not a web address or an app link.");
          return;
        }
        await wbSetItemLink(kind, item, link);
      }),
    ];
    const at = wbContextMoreWrap()?.getBoundingClientRect();
    const pages = wbFmtState.drawMore?.pageLinkItem((link) => wbSetItemLink(kind, item, link), at ? at.left : 80, at ? at.bottom + 4 : 80);
    if (pages) items.push(pages);
    if (now) {
      items.push(makeMenuItem("ph:arrow-square-out Open the link", wbFmtState.drawMore?.linkWords(now) || now, () => wbOpenItemLink(now)));
      items.push(makeMenuItem("ph:link-break Remove the link", "Take the link off; the shape stays", () => wbSetItemLink(kind, item, "")));
    }
    openMenuAtPoint(items, "Link", at ? at.left : 80, at ? at.bottom + 4 : 80);
  }

  //: The link marks, in their own host beside the comment marks and painted
  //: with them: a pin at the item's top-left corner, the button up and left of
  //: it, clear of the resize grip.
  function wbPaintLinkMarks() {
    const layer = document.getElementById("wb-html-layer");
    if (!layer) return;
    let host = document.getElementById("wb-link-marks");
    const wanted = [];
    for (const kind of ["object", "sketch"]) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
        const link = wbItemLink(kind, item);
        if (link) wanted.push([kind, item, link]);
      }
    }
    if (!wanted.length) {
      host?.replaceChildren();
      return;
    }
    if (!host) {
      host = document.createElement("div");
      host.id = "wb-link-marks";
      host.className = "wb-comment-marks";
      layer.appendChild(host);
    }
    //: Over every item: the card layer paints by stack rank (`wbStackRanks`).
    const top = wbStackOrder().length + 1;
    host.style.zIndex = String(top + 1);
    const old = new Map([...host.children].map((pin) => [pin.dataset.linkKey, pin]));
    for (const [kind, item, link] of wanted) {
      const key = wbMultiKey(kind, item.id);
      const box = typeof item._liveD === "string" ? wbPathBBox(item._liveD) : wbItemBBox(kind, item);
      if (!box) continue;
      let pin = old.get(key);
      old.delete(key);
      if (!pin) {
        pin = document.createElement("div");
        pin.className = "wb-comment-pin";
        pin.dataset.linkKey = key;
        const mark = document.createElement("button");
        mark.type = "button";
        mark.className = "wb-link-mark";
        const icon = document.createElement("i");
        icon.setAttribute("aria-hidden", "true");
        mark.appendChild(icon);
        mark.addEventListener("pointerdown", (event) => event.stopPropagation());
        mark.addEventListener("dblclick", (event) => event.stopPropagation());
        mark.addEventListener("click", (event) => {
          event.stopPropagation();
          wbOpenItemLink(mark.dataset.link);
        });
        pin.appendChild(mark);
        host.appendChild(pin);
      }
      const mark = pin.firstElementChild;
      const inApp = link.startsWith("#/");
      const pageWords = wbFmtState.drawMore?.linkWords(link);
      const words = pageWords || (inApp ? appAddressLabel(link) : link);
      mark.dataset.link = link;
      mark.firstElementChild.className = `ph ${pageWords ? "ph-presentation" : inApp ? "ph-note" : "ph-arrow-square-out"}`;
      mark.setAttribute("aria-label", `Open the link: ${words}`);
      mark.title = words;
      pin.style.left = `${box.minX}px`;
      pin.style.top = `${box.minY}px`;
    }
    for (const pin of old.values()) pin.remove();
  }

  //: The marks, from state, after every render and every drag frame (the
  //: selection bar's frame, `wbQueueSelectionBar`). A zero-size pin at the
  //: item's top-right corner, scaled back to screen size like a grip, holds
  //: the button up and to the right of the corner, clear of the resize handle.
  function wbPaintCommentMarks() {
    wbPaintLinkMarks();
    const layer = document.getElementById("wb-html-layer");
    if (!layer) return;
    //: A thread open on an item that is gone (deleted, another board) goes too.
    if (wbCommentState && !wbFindItem(wbCommentState.kind, wbCommentState.id)) wbCloseComments();
    let host = document.getElementById("wb-comment-marks");
    const wanted = [];
    for (const kind of ["node", "object", "sketch"]) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
        //: The mark counts what is still open; a thread that is all resolved
        //: keeps a quiet tick, so it can still be opened and read.
        //: A reply is as open as the comment it answers.
        const thread = wbItemComments(kind, item);
        const shut = new Set(thread.filter((c) => c.resolved).map((c) => c.id));
        if (thread.length) wanted.push([kind, item, thread.filter((c) => !shut.has(c.id) && !shut.has(c.reply_to)).length]);
      }
    }
    if (!wanted.length) {
      host?.replaceChildren();
      return;
    }
    if (!host) {
      host = document.createElement("div");
      host.id = "wb-comment-marks";
      host.className = "wb-comment-marks";
      layer.appendChild(host);
    }
    //: Over every item: the card layer paints by stack rank (`wbStackRanks`).
    const top = wbStackOrder().length + 1;
    host.style.zIndex = String(top + 1);
    const old = new Map([...host.children].map((pin) => [pin.dataset.commentKey, pin]));
    for (const [kind, item, count] of wanted) {
      const key = wbMultiKey(kind, item.id);
      const box = typeof item._liveD === "string" ? wbPathBBox(item._liveD) : wbItemBBox(kind, item);
      if (!box) continue;
      let pin = old.get(key);
      old.delete(key);
      if (!pin) {
        pin = document.createElement("div");
        pin.className = "wb-comment-pin";
        pin.dataset.commentKey = key;
        const mark = document.createElement("button");
        mark.type = "button";
        mark.className = "wb-comment-mark";
        mark.setAttribute("aria-haspopup", "dialog");
        mark.setAttribute("aria-expanded", "false");
        const icon = document.createElement("i");
        icon.className = "ph ph-chat-circle";
        icon.setAttribute("aria-hidden", "true");
        mark.append(icon, document.createElement("span"));
        mark.addEventListener("pointerdown", (event) => event.stopPropagation());
        mark.addEventListener("dblclick", (event) => event.stopPropagation());
        mark.addEventListener("click", (event) => {
          event.stopPropagation();
          wbOpenComments(kind, item.id, mark);
        });
        pin.appendChild(mark);
        host.appendChild(pin);
      }
      const mark = pin.firstElementChild;
      mark.lastElementChild.textContent = count ? String(count) : "";
      mark.classList.toggle("is-resolved", !count);
      mark.firstElementChild.className = `ph ${count ? "ph-chat-circle" : "ph-check"}`;
      const words = count ? `${count} open comment${count === 1 ? "" : "s"}` : "Every comment resolved";
      mark.setAttribute("aria-label", `${words}. Open the thread`);
      mark.title = words;
      pin.style.left = `${box.maxX}px`;
      pin.style.top = `${box.minY}px`;
    }
    for (const pin of old.values()) pin.remove();
  }



  function wbOpenComments(kind, id, anchor = null) {
    const item = wbFindItem(kind, id);
    if (!wbTakesComments(kind, item)) return;
    const key = wbMultiKey(kind, id);
    //: The mark is a toggle, as the help popover's own '?' is.
    if (wbCommentState?.key === key) {
      wbCloseComments();
      return;
    }
    wbCloseComments();
    const target = anchor?.isConnected
      ? anchor
      : document.querySelector(`.wb-comment-pin[data-comment-key="${key}"] .wb-comment-mark`) ||
        document.querySelector(WB_SELECTOR_BY_KIND[kind](id));
    if (!target) return;
    const panel = document.createElement("div");
    panel.className = "help-popover wb-comments";
    panel.id = "wb-comments";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Comments");
    const list = document.createElement("div");
    list.className = "wb-comments-list";
    list.setAttribute("role", "list");
    //: **The composer waits behind "New comment"** (INBOX 570, the owner: "the
    //: new comment form is permanently showing below, there should be a new
    //: comment option below for it to show"). A thread is for reading first:
    //: the comments, then one quiet button; the button reveals the box,
    //: focused, with Post and Cancel; Escape cancels, a post folds it away
    //: again. An empty thread has nothing to read, so it opens on the box.
    const newButton = document.createElement("button");
    newButton.type = "button";
    newButton.className = "ghost small wb-comments-new";
    newButton.setAttribute("aria-expanded", "false");
    setLabel(newButton, "ph:plus New comment");
    const composer = document.createElement("div");
    composer.className = "wb-comments-composer";
    composer.hidden = true;
    composer.id = "wb-comments-composer";
    newButton.setAttribute("aria-controls", composer.id);
    const box = document.createElement("textarea");
    box.className = "wb-comments-box";
    //: An editing surface (`EDITOR_SURFACES`, context "comment"): "/" offers
    //: links, bookmarks, a board, an emoji and the date, "[[" a note.
    box.id = "wb-comments-box";
    wbRegisterCommentSurfaces();
    box.rows = 2;
    box.maxLength = 2000;
    box.placeholder = "Write a comment, / for links";
    box.setAttribute("aria-label", "New comment");
    //: Shown while the box answers one comment; its X goes back to a new one.
    const replying = document.createElement("div");
    replying.className = "wb-comments-replying muted";
    replying.hidden = true;
    const replyingText = document.createElement("span");
    const replyingClear = smallButton("ph:x", "Not a reply", () => setReplyTo(null));
    replying.append(replyingText, replyingClear);
    let replyTo = null;
    const setReplyTo = (comment) => {
      replyTo = comment ? comment.id : null;
      replying.hidden = !comment;
      replyingText.textContent = comment ? `Replying to "${clipText(String(comment.text).replace(/\s+/g, " "), 48)}"` : "";
      box.setAttribute("aria-label", comment ? "Reply" : "New comment");
    };
    //: **Attach** (the owner, 2026-10-10: "attach bookmarks, web links and
    //: more in comments"): the app's one-thing picker, and what it hands back
    //: written into the box as the markdown the thread draws. A saved link
    //: goes on a line of its own, which `renderMarkdown` draws as the app's
    //: link card; a note, document or board is a `[[link]]` chip.
    const attach = smallButton("ph:paperclip Attach", "Attach a bookmark, note, document or board", async () => {
      if (typeof pickLibraryItemDialog !== "function") return;
      const chosen = await pickLibraryItemDialog("Attach to this comment", { sources: ["link", "note", "document", "board"] });
      if (!chosen) return;
      const piece = wbCommentAttachMarkdown(chosen);
      if (!piece) return;
      const at = box.selectionStart ?? box.value.length;
      const before = box.value.slice(0, at);
      const after = box.value.slice(box.selectionEnd ?? at);
      const lead = chosen.kind === "link" && before && !before.endsWith("\n") ? "\n" : before && !/\s$/.test(before) ? " " : "";
      const tail = chosen.kind === "link" ? "\n" : " ";
      box.value = `${before}${lead}${piece}${tail}${after}`.slice(0, box.maxLength);
      const caret = Math.min(box.value.length, (before + lead + piece + tail).length);
      box.focus({ preventScroll: true });
      box.setSelectionRange(caret, caret);
    });
    attach.classList.add("wb-comments-attach");
    const post = document.createElement("button");
    post.type = "button";
    post.className = "small wb-comments-post";
    post.textContent = "Post";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ghost small wb-comments-cancel";
    cancel.textContent = "Cancel";
    const foot = document.createElement("div");
    foot.className = "wb-comments-foot";
    const hint = document.createElement("span");
    hint.className = "muted";
    hint.textContent = "Enter posts, Shift+Enter breaks the line.";
    const actions = document.createElement("span");
    actions.className = "wb-comments-actions";
    actions.append(cancel, post);
    foot.append(attach, actions);
    composer.append(replying, box, hint, foot);
    panel.append(list, newButton, composer);
    const hasThread = () => wbItemComments(kind, wbFindItem(kind, id)).length > 0;
    const openComposer = (answering = null) => {
      setReplyTo(answering);
      composer.hidden = false;
      newButton.hidden = true;
      newButton.setAttribute("aria-expanded", "true");
      box.focus({ preventScroll: true });
    };
    //: Back to the button; with nothing in the thread there is nothing to go
    //: back to, so the popover closes instead.
    const closeComposer = () => {
      box.value = "";
      setReplyTo(null);
      if (!hasThread()) {
        wbCloseComments({ restoreFocus: true });
        return;
      }
      composer.hidden = true;
      newButton.hidden = false;
      newButton.setAttribute("aria-expanded", "false");
      newButton.focus({ preventScroll: true });
    };
    newButton.addEventListener("click", () => openComposer());
    cancel.addEventListener("click", closeComposer);
    const send = async () => {
      const text = box.value.trim();
      const now = wbFindItem(kind, id);
      if (!text || !now) {
        box.focus({ preventScroll: true });
        return;
      }
      const thread = wbItemComments(kind, now);
      if (thread.length >= WB_COMMENTS_MAX) {
        toast(`A thread holds ${WB_COMMENTS_MAX} comments. Delete one first.`, "info");
        return;
      }
      box.value = "";
      const made = { id: crypto.randomUUID ? crypto.randomUUID() : `c${Date.now()}${Math.random().toString(36).slice(2, 12)}`, text, at: new Date().toISOString() };
      //: A reply answers the thread's top comment (one level, as Miro and
      //: Figma draw it), and the parent must still be there.
      const parent = replyTo ? thread.find((c) => c.id === replyTo) : null;
      if (parent) made.reply_to = parent.reply_to && thread.some((c) => c.id === parent.reply_to) ? parent.reply_to : parent.id;
      await wbSetComments(kind, now, [...thread, made]);
      wbFillComments();
      list.querySelector(`[data-comment-id="${CSS.escape(made.id)}"]`)?.scrollIntoView({ block: "nearest" });
      closeComposer();
      wbAnnounce(parent ? "Reply added." : "Comment added.");
    };
    post.addEventListener("click", send);
    //: Every key typed here is the thread's: the board's keys stay out.
    panel.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Escape") {
        event.preventDefault();
        if (!composer.hidden) closeComposer();
        else wbCloseComments({ restoreFocus: true });
      } else if (event.key === "Enter" && !event.shiftKey && event.target === box) {
        //: The editor's own menu, open on the box, has taken an Enter already
        //: (`editorMenuState`, capture phase): this one is the post.
        event.preventDefault();
        send();
      }
    });
    const outside = (event) => {
      if (panel.contains(event.target) || target.contains(event.target)) return;
      wbCloseComments();
    };
    document.addEventListener("pointerdown", outside, true);
    document.body.appendChild(panel);
    wbCommentState = { key, kind, id, panel, anchor: target, outside, openComposer };
    if (target.classList.contains("wb-comment-mark")) target.setAttribute("aria-expanded", "true");
    wbFillComments();
    if (hasThread()) {
      placeHelpPopover(panel, target);
      newButton.focus({ preventScroll: true });
    } else {
      composer.hidden = false;
      newButton.hidden = true;
      placeHelpPopover(panel, target);
      box.focus({ preventScroll: true });
    }
  }

  //: The thread, oldest first, each reply under the comment it answers; each
  //: comment with its time, Reply, Edit, Resolve and Delete. Resolved threads
  //: fold into one "N resolved" disclosure at the foot (the owner, 2026-10-10:
  //: comments "need a lot of improvement"; decision 17 had no resolve, and
  //: deleting was the only way to close a point).
  function wbFillComments() {
    const state = wbCommentState;
    if (!state) return;
    const item = wbFindItem(state.kind, state.id);
    const list = state.panel.querySelector(".wb-comments-list");
    list.replaceChildren();
    const thread = wbItemComments(state.kind, item);
    if (!thread.length) {
      const empty = document.createElement("p");
      empty.className = "muted wb-comments-empty";
      empty.textContent = "No comments yet.";
      list.appendChild(empty);
      return;
    }
    const ids = new Set(thread.map((c) => c.id));
    const tops = thread.filter((c) => !c.reply_to || !ids.has(c.reply_to));
    const repliesOf = (c) => thread.filter((r) => r.reply_to === c.id);
    const open = tops.filter((c) => !c.resolved);
    const done = tops.filter((c) => c.resolved);
    for (const top of open) {
      list.appendChild(wbCommentRow(state, top, false));
      for (const reply of repliesOf(top)) list.appendChild(wbCommentRow(state, reply, true));
    }
    if (done.length) {
      const fold = document.createElement("details");
      fold.className = "wb-comments-resolved";
      if (state.showResolved || !open.length) fold.open = true;
      fold.addEventListener("toggle", () => { state.showResolved = fold.open; });
      const summary = document.createElement("summary");
      summary.textContent = `${done.length} resolved`;
      fold.appendChild(summary);
      for (const top of done) {
        fold.appendChild(wbCommentRow(state, top, false));
        for (const reply of repliesOf(top)) fold.appendChild(wbCommentRow(state, reply, true));
      }
      list.appendChild(fold);
    }
  }

  //: One comment: its words drawn by the app's own markdown (a link alone on
  //: a line is a link card, `[[a note]]` a chip), then its time and actions.
  function wbCommentRow(state, comment, isReply) {
    const row = document.createElement("div");
    row.className = "wb-comment";
    row.classList.toggle("wb-comment-reply", isReply);
    row.classList.toggle("is-resolved", Boolean(comment.resolved));
    row.dataset.commentId = comment.id;
    row.setAttribute("role", "listitem");
    const text = document.createElement("div");
    text.className = "wb-comment-text";
    //: A link on a line of its own is set apart as its own paragraph first:
    //: a comment is typed as lines ("See the spec", then the address), and
    //: the markdown reads two lines as one paragraph, which keeps a link inline.
    renderMarkdown(text, String(comment.text).split("\n").map((line) => (LONE_LINK.test(line) ? `\n${line}\n` : line)).join("\n"));
    wbCommentWikiChips(text);
    const meta = document.createElement("div");
    meta.className = "wb-comment-meta";
    const when = document.createElement("time");
    when.className = "muted";
    when.dateTime = comment.at || "";
    when.textContent = [comment.at ? relativeTime(comment.at) : "", comment.edited ? "edited" : ""].filter(Boolean).join(", ");
    if (comment.edited) when.title = `Edited ${relativeTime(comment.edited)}`;
    const tools = document.createElement("span");
    tools.className = "wb-comment-tools";
    //: Every change is the whole thread written back, one undo step, read
    //: fresh from state so a second panel action never writes a stale copy.
    const change = async (mutate, said) => {
      const now = wbFindItem(state.kind, state.id);
      if (!now) return;
      await wbSetComments(state.kind, now, mutate(wbItemComments(state.kind, now)));
      wbFillComments();
      if (said) wbAnnounce(said);
    };
    const reply = smallButton("ph:arrow-bend-up-left", "Reply", () => state.openComposer?.(comment));
    const edit = smallButton("ph:pencil-simple", "Edit this comment", () => wbEditCommentRow(state, row, comment, change));
    tools.append(reply, edit);
    if (!isReply) {
      const resolve = smallButton(
        comment.resolved ? "ph:arrow-counter-clockwise" : "ph:check-circle",
        comment.resolved ? "Reopen this comment" : "Resolve this comment",
        () => change(
          (list) => list.map((c) => (c.id === comment.id ? { ...c, resolved: comment.resolved ? undefined : true } : c)),
          comment.resolved ? "Comment reopened." : "Comment resolved. Ctrl+Z reopens it."
        )
      );
      tools.appendChild(resolve);
    }
    const del = smallButton("ph:trash", "Delete this comment", async () => {
      //: Its replies go with it: an answer to nothing reads as a stray.
      await change((list) => list.filter((c) => c.id !== comment.id && c.reply_to !== comment.id), "Comment deleted. Ctrl+Z brings it back.");
      //: The focus goes where the reader is: the button, or the box when
      //: the last comment went and the thread is empty again.
      const button = state.panel.querySelector(".wb-comments-new");
      const composer = state.panel.querySelector(".wb-comments-composer");
      if (!wbItemComments(state.kind, wbFindItem(state.kind, state.id)).length) {
        composer.hidden = false;
        button.hidden = true;
        state.panel.querySelector(".wb-comments-box")?.focus({ preventScroll: true });
      } else if (!button.hidden) {
        button.focus({ preventScroll: true });
      }
    });
    tools.appendChild(del);
    for (const button of tools.children) button.classList.add("icon-only");
    meta.append(when, tools);
    row.append(text, meta);
    return row;
  }

  //: Edit in place: the words become a box with the comment's own text, Enter
  //: (or Save) keeps it and stamps it edited, Escape (or Cancel) puts the words
  //: back. The box is an editing surface too, so "/" and "[[" work in it.
  function wbEditCommentRow(state, row, comment, change) {
    const text = row.querySelector(".wb-comment-text");
    const meta = row.querySelector(".wb-comment-meta");
    if (!text || row.querySelector(".wb-comments-edit")) return;
    const box = document.createElement("textarea");
    box.className = "wb-comments-box wb-comments-edit";
    box.id = "wb-comments-edit";
    wbRegisterCommentSurfaces();
    box.rows = Math.min(6, Math.max(2, String(comment.text).split("\n").length));
    box.maxLength = 2000;
    box.value = comment.text;
    box.setAttribute("aria-label", "Edit comment");
    const save = smallButton("Save", "Keep this edit", () => keep(), false);
    const cancel = smallButton("Cancel", "Put the comment back as it was", () => back());
    const actions = document.createElement("span");
    actions.className = "wb-comments-actions";
    actions.append(cancel, save);
    const back = () => {
      box.remove();
      actions.remove();
      text.hidden = false;
      meta.hidden = false;
      row.querySelector(".wb-comment-tools [aria-label='Edit this comment']")?.focus({ preventScroll: true });
    };
    const keep = async () => {
      const next = box.value.trim();
      if (!next) {
        box.focus({ preventScroll: true });
        return;
      }
      if (next === comment.text) return back();
      await change((list) => list.map((c) => (c.id === comment.id ? { ...c, text: next, edited: new Date().toISOString() } : c)), "Comment edited.");
    };
    box.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        event.stopPropagation();
        keep();
      } else if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        back();
      }
    });
    text.hidden = true;
    meta.hidden = true;
    row.append(box, actions);
    box.focus({ preventScroll: true });
    box.setSelectionRange(box.value.length, box.value.length);
  }

  //: `renderMarkdown` is the answer renderer and leaves `[[a note]]` as text;
  //: the note card's own inline renderer draws it as the chip that opens the
  //: note, document or board. Applied to the text runs only, never inside a
  //: link or code.
  function wbCommentWikiChips(root) {
    if (typeof renderNoteInline !== "function") return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => (node.data.includes("[[") && !node.parentElement?.closest("a, code, pre") ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    const runs = [];
    while (walker.nextNode()) runs.push(walker.currentNode);
    for (const run of runs) {
      const span = document.createElement("span");
      renderNoteInline(span, run.data, []);
      run.replaceWith(span);
    }
  }

  //: What an attached thing is written as in a comment.
  function wbCommentAttachMarkdown(chosen) {
    const row = chosen.row || {};
    const label = String(chosen.label || row.title || "").replace(/[[\]|]/g, " ").replace(/\s+/g, " ").trim().slice(0, 120);
    if (chosen.kind === "link") {
      const url = String(row.url || "").replace(/ /g, "%20").replace(/\)/g, "%29");
      return url ? `[${label || url}](${url})` : "";
    }
    if (chosen.kind === "board") return `[[${row.type === "board" ? "board" : "map"}:${chosen.id ?? row.id}|${label || "Board"}]]`;
    return label ? `[[${label}]]` : "";
  }

  //: The two comment boxes are editing surfaces of their own context.
  function wbRegisterCommentSurfaces() {
    if (typeof EDITOR_SURFACES !== "object") return;
    wbRegisterEditorContexts();
    EDITOR_SURFACES["wb-comments-box"] = "comment";
    EDITOR_SURFACES["wb-comments-edit"] = "comment";
  }

  function wbCloseComments({ restoreFocus = false } = {}) {
    const state = wbCommentState;
    if (!state) return;
    wbCommentState = null;
    document.removeEventListener("pointerdown", state.outside, true);
    state.panel.remove();
    if (state.anchor.classList.contains("wb-comment-mark")) state.anchor.setAttribute("aria-expanded", "false");
    if (restoreFocus) {
      const mark = document.querySelector(`.wb-comment-pin[data-comment-key="${state.key}"] .wb-comment-mark`);
      (mark || document.getElementById("whiteboard-container"))?.focus({ preventScroll: true });
    }
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbTakesComments, wbItemComments, wbFindItem, wbTakesLink, wbItemLink, wbEditItemLink, wbPaintCommentMarks, wbOpenComments, wbCloseComments });
})();
