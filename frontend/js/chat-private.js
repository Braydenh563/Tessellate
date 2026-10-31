// A private chat (INBOX 1481), loaded by `chatPrivate` (lazy-entries.js) on the first
// press of its switch.
//: **A chat that is not kept** (the owner: "privat chat sessions might be
//: good??"). While `chatConv.private` is on: no row is written (the three
//: writes in chat-attach.js's `chatSendTurn` skip it), the turn goes to the
//: server marked `private` (`streamChatEvents`' `isPrivate`), which keeps
//: nothing of it (`ChatRequest.private`, routes_chat.py), and the transcript
//: lives in this page only. The answer still comes from the notes.
//:
//: Three ways in, one function: the switch in the composer's settings, the
//: chat head's ⋯ and the palette's "Private chat". Leaving a private chat that
//: has messages (New chat, another chat, Delete, closing the page) asks once
//: and then discards it.
const PRIVATE_EMPTY_LINE = "Private chat. Nothing here is saved or remembered.";

//: The empty pane, in place of the welcome and the starters: one line.
function chatPrivateEmpty(box) {
  const empty = document.createElement("div");
  empty.className = "chat-empty chat-empty-private";
  const glyph = document.createElement("i");
  glyph.className = "ph ph-ghost";
  glyph.setAttribute("aria-hidden", "true");
  const line = document.createElement("p");
  line.className = "muted chat-empty-line";
  line.textContent = PRIVATE_EMPTY_LINE;
  empty.append(glyph, line);
  box.appendChild(empty);
}

function chatPrivateRepaint() {
  clearChatEmptyState();
  $("chat-messages").replaceChildren();
  renderChatEmptyState();
  syncChatPrivate();
}

//: Switch the open, empty chat to private in place, or start a fresh one first.
function chatPrivateStart() {
  if (chatConv.private) return;
  const fresh = chatConv.id === null && !chatConv.turns.length && !chatStreaming;
  if (!fresh) newChatConversation();
  chatConv.private = true;
  chatPrivateRepaint();
  $("chat-input").focus();
}

//: The one switch: on starts one, on a private chat it ends it.
function chatPrivateToggle() {
  if (!chatConv.private) return chatPrivateStart();
  if (chatConv.turns.length || chatStreaming?.conv === chatConv) return newChatConversation();
  chatConv.private = false;
  chatPrivateRepaint();
}

//: Asked once, then gone: a stream still running is stopped, the messages are
//: dropped, and `retry` (the New chat or the chat that was being opened) goes on.
async function chatPrivateLeave(retry) {
  const ok = await confirmDialog("Discard this private chat? Its messages are not saved anywhere.", {
    confirmLabel: "Discard",
  });
  if (!ok) return;
  chatController?.abort();
  chatConv = { id: null, turns: [] };
  retry();
}

//: A closed tab is a closed chat: the browser asks before it goes.
window.addEventListener("beforeunload", (event) => {
  if (chatConv.private && chatConv.turns.length) event.preventDefault();
});
