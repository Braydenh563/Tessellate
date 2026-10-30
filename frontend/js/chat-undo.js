// The chat's undo helpers (CHAT_PLAN 8 row 5, decision 53), loaded by
// `chatUndo` in chat-attach.js on the first chat write.
//: **Every chat write is on the undo bar** (CHAT_PLAN 8 row 5, decision 53):
//: a rename, a pin, an archive, a fork, a saved document and a deleted
//: message each name their own inverse, and the list repaints both ways.
function chatRepaint(step) {
  return async () => {
    await step();
    loadConversationList();
  };
}

function chatPut(path, body) {
  return apiJson(`/conversations/${path}`, { method: "PUT", ...(body ? { body: JSON.stringify(body) } : {}) });
}

//: Rename, pin and archive toast with Undo, as delete does (A32); `said` replaces the default sentence.
function chatTitleUndo(id, before, after, said) {
  const name = (title) => async () => {
    await chatPut(id, { title });
    if (chatConv?.id === id) $("chat-title").textContent = title;
  };
  offerUndo(`Renamed the chat to “${after}”`, said || `Renamed to “${after}”.`, chatRepaint(name(before)), chatRepaint(name(after)));
}

function chatPinUndo(id, pinned) {
  const pin = (to) => chatRepaint(() => chatPut(`${id}/pin`, { pinned: to }));
  offerUndo(pinned ? "Pinned a chat" : "Unpinned a chat", pinned ? "Pinned." : "Unpinned.", pin(!pinned), pin(pinned));
}

function chatArchiveUndo(id, title) {
  offerUndo(`Archived “${title}”`, "Archived. Find it in Library, Archived.", chatRepaint(() => chatPut(`${id}/unarchive`)), chatRepaint(() => chatPut(`${id}/archive`)));
}

//: A fork is a new chat, so its undo deletes it and keeps the row the DELETE
//: answers with, which is what its redo sends back.
function chatForkUndo(fork) {
  let row = null;
  pushUndo(
    `Forked to “${fork.title}”`,
    chatRepaint(async () => {
      row = (await apiJson(`/conversations/${fork.id}`, { method: "DELETE" })).restore;
      if (chatConv?.id === fork.id) newChatConversation();
    }),
    chatRepaint(() => apiJson("/conversations/restore", { method: "POST", body: JSON.stringify(row) }))
  );
}

function chatDocumentUndo(doc) {
  pushUndo(
    `Saved “${doc.title}” to your documents`,
    () => apiJson(`/documents/${doc.id}`, { method: "DELETE" }),
    () => apiJson(`/documents/${doc.id}/restore`, { method: "POST" })
  );
}

//: A deleted message comes back at its own place: the DELETE answers with the
//: pair it removed (`POST .../turns/{i}/restore`), or, when it was the chat's
//: last, with the whole row. The open chat is reread either way.
function chatTurnUndo(id, index, gone) {
  const reopen = () => (chatConv?.id === id || chatConv?.id === null ? openConversation(id) : null);
  const back = gone.conversation_deleted
    ? () => apiJson("/conversations/restore", { method: "POST", body: JSON.stringify(gone.restore) })
    : () => apiJson(`/conversations/${id}/turns/${index}/restore`, { method: "POST", body: JSON.stringify({ messages: gone.removed }) });
  offerUndo(
    "Deleted a message",
    "Message deleted.",
    async () => { await back(); await reopen(); loadConversationList(); },
    async () => {
      await apiJson(`/conversations/${id}/turns/${index}`, { method: "DELETE" });
      if (chatConv?.id === id) await (gone.conversation_deleted ? newChatConversation() : openConversation(id));
      loadConversationList();
    }
  );
}

//: **Editing a question and resending it** (INBOX 898): the old wording and
//: its replies were cut off (`cut`, the truncate's answer) and a new tail
//: written. Undo swaps the tails back and Redo swaps them again, each side
//: kept as the server's own record of what it just removed. When the cut took
//: the whole chat, the new chat is another row and the two rows swap instead.
function chatEditUndo(id, turnIndex, cut, newId) {
  const whole = Boolean(cut.conversation_deleted);
  const post = (path, body) => apiJson(`/conversations/${path}`, { method: "POST", body: JSON.stringify(body) });
  const cutAt = async () => (await post(`${id}/truncate`, { from_turn: turnIndex })).removed_messages || [];
  const putBack = (messages) => (messages.length ? post(`${id}/truncate/restore`, { from_turn: turnIndex, messages }) : null);
  const reopen = async (open) => {
    loadConversationList();
    if (open == null) newChatConversation();
    else await openConversation(open);
  };
  let oldRow = cut.restore;
  let oldTail = cut.removed_messages || [];
  let newRow = null;
  let newTail = [];
  pushUndo(
    "Edited a question and resent it",
    async () => {
      if (whole) {
        if (newId != null) newRow = (await apiJson(`/conversations/${newId}`, { method: "DELETE" })).restore;
        await post("restore", oldRow);
        await reopen(oldRow.id);
      } else {
        newTail = await cutAt();
        await putBack(oldTail);
        await reopen(id);
      }
    },
    async () => {
      if (whole) {
        oldRow = (await apiJson(`/conversations/${oldRow.id}`, { method: "DELETE" })).restore;
        if (newRow) await post("restore", newRow);
        await reopen(newRow?.id ?? null);
      } else {
        oldTail = await cutAt();
        await putBack(newTail);
        await reopen(id);
      }
    }
  );
}
