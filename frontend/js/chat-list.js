// chat-list.js: the chat switcher's list and the opening of one chat. Moved
// out of sheets-selects.js on 2026-11-21 (the boot-script gzip budget, ratchet
// in tests/test_static_compression.py): both are async and reached by a chat
// tab, a search hit or a press, so `LAZY_ENTRY_POINTS.chatList` (lazy-entries.js)
// stands in for them until the first call fetches this file.

async function loadConversationList() {
  //: Placeholders while the list is on its way, and no "no saved chats"
  //: until the answer says so (INBOX 435 (6), skeletons.js).
  const list = $("conversation-list");
  showSkeletons(list, 4, "li");
  if (!list.children.length || list.querySelector(".skeleton")) $("conv-empty")?.classList.add("hidden");
  //: A failed read says so with Try again; "No saved chats yet" is for a list that came back empty.
  //: The search box asks the server, which reads titles and message text (E47).
  const term = $("chat-sidebar-search").value.trim();
  const asked = (loadConversationList.n = -~loadConversationList.n); // the newest read owns the list
  const loaded = await loadSurface($("conv-empty"), "your chats", () => apiJson(`/conversations?q=${encodeURIComponent(term)}`));
  clearSkeletons(list);
  if (asked !== loadConversationList.n) return;
  if (!loaded) return list.replaceChildren();
  const conversations = sortConversations(loaded, $("chat-sidebar-sort")?.value || "recent", term ? 4 * RECENT_CHATS_SHOWN : RECENT_CHATS_SHOWN);
  list.replaceChildren();
  const empty = $("conv-empty");
  empty.classList.toggle("hidden", conversations.length > 0);
  //: The empty-state recipe (icon, title, one sentence, one action), drawn here and not
  //: shipped in the page (the boot element cap); the grey line it replaces had none of them.
  if (!conversations.length) {
    const icon = document.createElement("span");
    icon.className = "empty-icon";
    icon.setAttribute("aria-hidden", "true");
    setLabel(icon, "ph:chats");
    const title = document.createElement("p");
    title.className = "empty-title";
    title.textContent = term ? "No chats match" : "No saved chats yet";
    const hint = document.createElement("p");
    hint.textContent = term ? "The search reads titles and what was said." : "Ask something to start one.";
    empty.replaceChildren(icon, title, hint);
    if (!term) {
      const start = document.createElement("button");
      start.type = "button";
      start.className = "ghost small";
      start.dataset.emptyAction = "new-chat";
      setLabel(start, "ph:plus New chat");
      empty.appendChild(start);
    }
  }

  let sawUnpinned = false;
  for (const conversation of conversations) {
    // One divider between the pinned block and the rest, so "pinned" reads as
    // a section rather than as an unexplained reordering.
    if (!conversation.pinned && !sawUnpinned && list.children.length) {
      const rule = document.createElement("li");
      rule.className = "conv-divider";
      rule.setAttribute("aria-hidden", "true");
      list.appendChild(rule);
    }
    if (!conversation.pinned) sawUnpinned = true;

    const li = document.createElement("li");
    if (conversation.id === chatConv.id) li.classList.add("active-conv");
    if (conversation.pinned) li.classList.add("pinned-conv");

    //: **The whole row opens the chat, not just the words in it.** Reported:
    //: "I clicked on other chat conversations in the chat sidebar but the
    //: conversations didnt visibly select in the sidebar." Measured: the
    //: `<li>` is 268x48 and `.conv-title`, which carried the only click
    //: handler: is 211x35. The 6.4px/9.6px padding ring and the gutter kept
    //: clear for the ⋯ are dead: `elementFromPoint` returns the `<li>` at the
    //: row's top edge, bottom edge, left edge and right-hand side alike. So
    //: roughly a third of every row did nothing when clicked, which reads
    //: exactly like a selection that failed rather than a click that missed.
    //:
    //: On the `<li>`, with the actions cluster excluded: a click on the ⋯ (or
    //: on anything inside the menu it opens) is not a request to switch
    //: conversations. `aria-current` says which row is the open one to a
    //: screen reader, which the accent fill says to everyone else.
    li.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest(".entry-actions")) return;
      openConversation(conversation.id);
    });
    li.setAttribute("aria-current", conversation.id === chatConv.id ? "true" : "false");

    const title = document.createElement("span");
    title.className = "conv-title";
    title.title = "Open this chat";
    //: The row opened on a click only (audit 1028 E36): the title is the
    //: keyboard's way in, Enter or Space, beside the row's own ⋯ button.
    title.tabIndex = 0;
    title.setAttribute("role", "button");
    title.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openConversation(conversation.id);
    });

    const name = document.createElement("span");
    name.className = "conv-name";
    setLabel(name, `${conversation.pinned ? "ph:push-pin " : ""}${conversation.title}`);
    const meta = document.createElement("span");
    meta.className = "conv-meta muted";
    const bits = [relativeTime(conversation.last_at)];
    if (conversation.turns) {
      bits.push(`${conversation.turns} ${conversation.turns === 1 ? "turn" : "turns"}`);
    }
    // "tok" rather than "tokens": the row is one line by design, and the
    // number is the useful part, spelling out the unit is what pushed it
    // into an ellipsis at the default sidebar width.
    if (conversation.tokens) bits.push(`${formatTokens(conversation.tokens)} tok`);
    meta.textContent = bits.join(" · ");
    //: The hover holds the exact time (OPEN #593); the row reads relative.
    meta.title = [parseServerTime(conversation.last_at)?.toLocaleString(undefined, { dateStyle: "full", timeStyle: "short" }), ...bits.slice(1)].filter(Boolean).join(" · ");
    title.append(name, meta);
    // The title often isn't the subject: show what was actually asked.
    if (conversation.preview && conversation.preview !== conversation.title) {
      title.title = conversation.preview;
    }
    // One ⋯ instead of three buttons. In a sidebar this narrow they were
    // taking most of the row, leaving a few characters of the chat's name.
    const actions = document.createElement("span");
    actions.className = "entry-actions";
    const items = [];
    items.push(
      makeMenuItem(
        conversation.pinned ? "ph:push-pin-slash Unpin" : "ph:push-pin Pin",
        conversation.pinned ? "Let this chat sort by date again" : "Keep this chat at the top",
        async () => {
          await apiJson(`/conversations/${conversation.id}/pin`, {
            method: "PUT",
            body: JSON.stringify({ pinned: !conversation.pinned }),
          });
          chatWriteRecord("chatPinUndo", conversation.id, !conversation.pinned);
          loadConversationList();
        }
      )
    );
    items.push(
      makeMenuItem("ph:pencil-simple Rename", "Rename this chat", async () => {
        const next = await promptTitle("Rename this chat", conversation.title);
        if (!next) return;
        await apiJson(`/conversations/${conversation.id}`, {
          method: "PUT",
          body: JSON.stringify({ title: next }),
        });
        chatWriteRecord("chatTitleUndo", conversation.id, conversation.title, next);
        if (chatConv.id === conversation.id) $("chat-title").textContent = next;
        loadConversationList();
      })
    );
    items.push(
      makeMenuItem("ph:sparkle Name with Atlas", "Let Atlas name this chat", async () => {
        //: Asked for, so answered directly: the activity notice below obeys
        //: "AI activity: panel only", and with that set the click showed
        //: nothing at all, start or finish (the owner at release).
        toast("Atlas is naming this chat…");
        const named = await apiJson(`/conversations/${conversation.id}/retitle`, {
          method: "POST",
        }).catch((e) => {
          toast(e.message, true);
          return null;
        });
        if (!named) return;
        if (chatConv.id === conversation.id) $("chat-title").textContent = named.title;
        if (named.title === conversation.title) toast("Kept the first question as the title.");
        else chatWriteRecord("chatTitleUndo", conversation.id, conversation.title, named.title, named.ai_named ? `Named “${named.title}”.` : "Used the first question as the title.");
        loadConversationList();
      })
    );
    items.push(appLinkMenuItem("chat", conversation.id));
    items.push(
      // Not destructive, so not grouped with Delete below, same "keep it,
      // but out of the way" action Notes already has for entries (BACKLOG
      // §30b's named remaining scope: chats and documents). Reachable
      // again from the Library's Shelved filter.
      makeMenuItem("ph:archive Archive", "Keep it, but out of the way, not deleted", async () => {
        await apiJson(`/conversations/${conversation.id}/archive`, { method: "PUT" });
        if (chatConv.id === conversation.id) newChatConversation();
        //: Awaited, so the row is gone by the time the toast says where it went (AI21).
        await loadConversationList();
        chatWriteRecord("chatArchiveUndo", conversation.id, conversation.title);
      })
    );
    items.push(
      makeMenuItem("ph:trash Delete", "Delete this chat", async () => {
        if (!(await confirmDialog("Delete this saved chat?"))) return;
        const gone = await apiJson(`/conversations/${conversation.id}`, { method: "DELETE" });
        if (chatConv.id === conversation.id) newChatConversation();
        loadConversationList();
        chatDeleteUndo(gone);
      })
    );
    //: Six rows is past the ceiling (DESIGN.md): what you do to it, its address, and the two that put it away.
    const group = (item) => (/Copy app link/.test(item.label) ? "copy" : /Archive|Delete/.test(item.label) ? "end" : "act");
    actions.appendChild(kebabMenu(items.map((item) => ({ ...item, group: group(item) })), `Actions for ${conversation.title}`, { vertical: true }));
    li.append(title, actions);
    list.appendChild(li);
  }
}

async function openConversation(id) {
  if (chatLeaveHeld(() => openConversation(id))) return;
  const full = await apiJson(`/conversations/${id}`).catch(() => null);
  if (!full) return;
  //: The replayed run is drawn by `agentTimeline`, in the chat turn's lazy file.
  if (!(await ensureModule("chatTurn"))) return lazyLoadFailed();
  // Before the pane is rebuilt, not after: this reads the composer state that
  // belongs to the conversation being left.
  releaseChatComposer();
  // ROADMAP.md item 13: switching between saved chats was invisible to
  // back/forward. Recorded here rather than at each of this function's
  // call sites (the sidebar, the Library) so neither has to remember to.
  recordTabVisit("chat", `conv:${full.id}`, full.title || "");
  chatConv = { id: full.id, turns: [] };
  syncChatPrivate();
  chatAwaitingAgentAnswer = false; // a saved thread's own pending ask, if any, isn't answerable live
  // Not carried across conversations, and not persisted: re-deriving it is one
  // click, and a summary restored against the wrong thread would be worse than
  // no summary at all.
  chatSummary = null;
  renderCompressionState();
  $("chat-title").textContent = full.title;
  renderChatUsage(full.tokens);
  //: **Give the starter chips back before clearing the pane, not after.**
  //:
  //: Reported with a screenshot: *"I cant view older chat sessions, the
  //: panel/page just appears blank."* The title, model and token count in the
  //: header were all correct, only the transcript was empty, which is what
  //: made it look like a rendering problem with the messages rather than a
  //: crash.
  //:
  //: `#chat-suggest` is **on loan**. `chatEmptyState` *moves* that element out
  //: of the dock and into `.chat-empty` inside `#chat-messages` (see its own
  //: comment on why the starters belong with the welcome). So on any chat that
  //: was showing the empty state, every fresh load of the tab, the element
  //: is a child of the very thing being wiped here: `replaceChildren()`
  //: destroyed it, and the next line dereferenced `null` and threw.
  //:
  //: The throw landed exactly between "clear the transcript" and "render the
  //: messages", so the pane was emptied and then nothing was drawn. Every
  //: saved conversation opened blank, and the console error was the only
  //: sign.
  //:
  //: `clearChatEmptyState` already knows how to return the chips to the dock, 
  //: it exists for this, so the fix is to let it run first rather than to
  //: null-guard the symptom.
  clearChatEmptyState();
  $("chat-messages").replaceChildren();
  //: Optional-chained regardless: this element is moved between two parents at
  //: runtime, and a second caller that clears the pane should degrade to a
  //: stale chip strip rather than to a blank conversation.
  $("chat-suggest")?.classList.add("hidden");
  let lastQuestionText = null;
  for (const message of full.messages) {
    if (message.role === "user") {
      lastQuestionText = message.content;
      const asked = addBubble("user", message.content, message.attachments);
      if (message.followup_of) markFollowup(asked, message.followup_of);
    } else {
      const handles = addAssistantBubble(message.persona || null);
      // Replay the run in the order it happened when the turn recorded one.
      // Older turns (saved before steps existed) only have the flattened
      // thinking/tools/answer, so they're rebuilt in that fixed order, 
      // everything is still shown, just without the interleaving.
      if (message.steps?.length) {
        handles.timeline.replay(message.steps);
      } else {
        if (message.thinking) handles.timeline.thinking(message.thinking);
        // Re-draw the tool-activity chips (Wave G) so they don't vanish on
        // reload the way they used to (user-reported).
        for (const t of message.tools || []) {
          handles.timeline.tool(toolChip(t.label, t.ok !== false, t));
        }
        if (message.content) handles.timeline.answer(message.content);
      }
      handles.timeline.finalise();
      //: …and the step group, so a replayed turn does not reopen with
      //: "Working: 3 steps" over a conversation that finished yesterday.
      handles.timeline.finish?.();
      // Rebuild the metadata line. Reported in the retired IDEAS.md as "chat message
      // metadata disappears on reload": it was only ever built from the live
      // stream, so reopening a chat showed answers with nothing to say which
      // model wrote them or what they cost. Turns saved before this stored no
      // stats and correctly get no line, rather than a row of "?"s.
      //: Badge and note card as the live answer drew them (INBOX 1693): `by` is saved with the reply.
      const by = message.by;
      if (by) finishReply(null, { ...by, bubble: handles.bubble, why: message.why, records: handles.recordsHolder });
      //: A reopened conversation gets its meter back from the last turn that recorded one.
      if (message.stats) renderChatContextMeter(message.stats);
      if (message.wrote) handles.bubble.dataset.wrote = "1";
      if (message.stats || by) {
        handles.bubble.appendChild(
          messageMetaLine({
            ...message, // stats and stopped, as saved
            model: (message.stats || by).model,
            elapsedMs: message.elapsed_ms,
            toolCount: (message.tools || []).length,
            rounds: (message.stats || by).round || 0,
            usedTools: message.used_tools,
          })
        );
      }
      //: The Sources panel is rebuilt, not the old "N matching notes" disclosure; `touched` comes off the saved tool events.
      const savedInput = {
        meta: {
          raw_results: message.raw_results || [],
          search_mode: message.search_mode,
        },
        toolEvents: message.tools || [],
        touched: (message.tools || []).flatMap((t) => t.touched || []),
        sentences: message.sentence_grounding,
        composed: Boolean(message.by?.composed),
      };
      //: The panel's order, built once and handed to the citation pass below
      //: as the live path does (chat-attach.js, `turnSources`). Reopening
      //: passed `null` there, so the marks fell back to "order first cited"
      //: and a note that was 8 in the panel read 1 in the prose while its
      //: peek showed source 8 (the owner, INBOX 430).
      const savedOrder = chatSourcesFrom(savedInput);
      const savedSources = chatSourcesPanel({ ...savedInput, sources: savedOrder });
      if (savedSources) {
        handles.recordsHolder.appendChild(savedSources);
      } else if (message.raw_results) {
        renderRecordsDetails(handles.recordsHolder, { ...message, match_info: message.match_info || {}, connected_ids: message.connected_ids || [] });
      }
      // Same reload-reconstruction fix as raw_results just above, for the
      // "Grounded in" chips: reported directly as disappearing once the chat
      // tab was left or the session ended, since nothing rebuilt this on
      // reopen either.
      if (message.sentence_grounding) {
        renderAnswerGrounding(
          handles.groundingHolder,
          message.sentence_grounding,
          message.raw_results || [],
          handles.bubble?.querySelectorAll(".bubble-answer") || null,
          "",
          savedOrder,
          //: Saved on the turn by the server from the same counter the live
          //: stream used, so the notice survives reopening the chat.
          message.support || null,
          message.picture_alts || null
        );
      }
      placeAnswerFigures(handles.bubble?.querySelectorAll(".bubble-answer"), message, lastQuestionText);
      // And the same shape again for the "what to ask next" chips, reported
      // separately: "suggested repsponse continuation prompts in chat doesnt
      // persist and disappears once I switch chat sessions or quit the app".
      // Rendered through the same function the live path uses, so a restored
      // chip is not a slightly different chip.
      if (message.followups) {
        renderFollowups(handles.bubble, message.followups);
      }
      renderToolConfirm.saved(handles, message);
      //: And the Resume and Edit-step buttons, which disappeared on reopen for
      //: the same reason and are rebuilt through the same function the live
      //: path uses, from the state saved with the turn.
      if (message.resume) {
        appendRunResumeControls(handles.bubble, {
          ...message.resume,
          timeline: handles.timeline,
        });
      }
      const turnIndex = chatConv.turns.length; // index this pair will occupy
      if (message.edited) handles.bubble.appendChild(editedMarker());
      //: The same list the live stream builds, see `assistantMessageActions`.
      //: These two paths had already drifted (this one had Edit and no fork or
      //: rewrite; the live one the reverse), which is how a fix lands on half
      //: the app's messages.
      assistantMessageActions({
        bubble: handles.bubble,
        text: message.content,
        question: lastQuestionText,
        onEdit: () => editChatAnswer(handles, turnIndex, message.content),
      });
      if (lastQuestionText !== null) {
        chatConv.turns.push({ question: lastQuestionText, answer: message.content, objects: message.objects, frame: message.frame });
      }
    }
  }
  // A conversation that is still being answered has not saved that turn yet, 
  // the save happens when the stream ends, so what came back from the server
  // above is the thread *without* the message in flight. Left alone, coming
  // back to it shows either an empty pane or a thread missing its newest
  // question: exactly the "my message disappeared" this whole change is about.
  // Saying so is the honest render, and the note is replaced by the real turn
  // the moment the stream finishes and the list refreshes.
  if (isStreamingConversation(full.id)) {
    // Coming back to the thread that is still being answered. The saved
    // messages above are the thread *without* this turn, it has not been
    // written yet, or exists only as a half-finished checkpoint row, which is
    // the reported "empty message bubble". Drop that partial and put the live
    // nodes back instead.
    const lastAssistant = [...$("chat-messages").querySelectorAll(".msg.assistant")].pop();
    if (lastAssistant && !lastAssistant.textContent.trim()) {
      const asked = lastAssistant.previousElementSibling;
      if (asked?.matches(".msg")) asked.remove();
      lastAssistant.remove();
    }
    reattachStreamingTurn();
  } else if (!full.messages.length) {
    renderChatEmptyState();
  }
  if (lastQuestionText) lastChatQuestion = lastQuestionText;
  renderChatTurnCount();
  lazyScript("/js/chat-time.js").then(() => stampChatTimes(full.messages));
  loadConversationList();
  //: Where it was left, not always its end (Placed 2026-09-09 item 99 (b)).
  if (isStreamingConversation(full.id)) chatScrollToEnd();
  else restoreChatPosition(full.id);
}
