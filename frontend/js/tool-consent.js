// tool-consent.js: the agent asking before it changes something, as a turn of the chat
// (L-world-class-181). Fetched by `renderToolConfirm` (answer-kit.js) on the first card, so no
// boot script carries it. The card says what Atlas would do and why, and offers Allow, Allow
// always for this chat (only for a change, never a removal) and Decline, which asks what to do
// instead. An edit to a note or a document is drawn as a suggestion, one hunk per change, each
// kept or skipped (`docRenderDiff`, documents-history.js); the press names the skipped hunks and
// the server leaves those lines as they were (`ToolExecuteBody.skip_hunks`). The server's guard
// is unchanged: every press, an "always" one too, spends the card's own consent id.

(() => {
  //: `<chat>:<tool>` pairs the person allowed for the rest of a chat. Page memory only: a reload
  //: asks again, which is the safe side of forgetting.
  const toolConsentAlways = new Set();

  function toolConsentKey(name) {
    return `${chatConv?.id || "new"}:${name}`;
  }

  //: The tools whose card draws the edit as a suggestion, and where the text it replaces lives.
  const TOOL_CONSENT_EDITS = {
    edit_note: (args) => `/entries/${Number(args.note_id) || 0}`,
    edit_document: (args) => `/documents/${Number(args.document_id) || 0}`,
  };

  async function toolConsentSuggestion(event, host) {
    const where = TOOL_CONSENT_EDITS[event.name];
    const after = event.arguments?.content;
    if (!where || typeof after !== "string") return null;
    const [loaded, current] = await Promise.all([lazyScript("/js/documents-history.js"), apiJson(where(event.arguments)).catch(() => null)]);
    if (!loaded || !current) return null;
    const ops = docDiffLines(current.content || "", after);
    const hunks = docDiffHunks(ops);
    const skipped = new Set();
    const head = document.createElement("p");
    head.className = "muted tool-consent-head";
    const view = document.createElement("div");
    view.className = "tool-consent-diff";
    //: `kept` is the text the press saves, built here where documents-history.js is known loaded.
    const suggestion = { before: current.content || "", ops, skipped, hunks, onChange: () => {}, kept: () => docDiffApply(ops, hunks, skipped), redraw: () => draw() };
    const draw = () => {
      const kept = hunks.length - skipped.size;
      head.textContent = hunks.length === 1 ? "One change. Skip it to leave the text as it is." : `${kept} of ${nounCount(hunks.length, "change")} kept. Skip any you don't want.`;
      const scroll = view.scrollTop;
      docRenderDiff(view, ops, { hunks, skipped, onToggleHunk: toggle, emptyText: "No change: the text would stay the same." });
      view.scrollTop = scroll;
      suggestion.onChange();
    };
    function toggle(index) {
      if (skipped.has(index)) skipped.delete(index);
      else skipped.add(index);
      draw();
    }
    host.replaceChildren(head, view);
    draw();
    return suggestion;
  }

  //: The same edit marked in the editor when its document is the one open (L-documents-41,
  //: doc-agent-review.js): its Accept and Reject share this card's `skipped`, and its last
  //: decision presses this card's Allow or Decline, so the save is still the card's press.
  async function toolConsentInEditor(event, suggestion, answers) {
    const id = Number(event.arguments?.document_id) || 0;
    if (event.name !== "edit_document" || typeof currentDoc === "undefined" || currentDoc?.id !== id) return null;
    const loaded = await Promise.all([lazyScript("/js/doc-agent-review.js"), lazyScript("/css/doc-agent-review-lazy.css")]);
    if (!loaded.every(Boolean)) return null;
    return drawToolConsent.inEditor({ documentId: id, before: suggestion.before, ops: suggestion.ops, hunks: suggestion.hunks, skipped: suggestion.skipped, onDecide: suggestion.redraw, ...answers });
  }

  //: Decline is a turn too: it says nothing ran, then asks what Atlas should do instead.
  function toolConsentInstead(card, event) {
    const done = toolChip("ph:x Declined: nothing was changed.");
    const form = document.createElement("form");
    form.className = "tool-consent-instead";
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = 500;
    input.placeholder = "What should Atlas do instead?";
    input.setAttribute("aria-label", "What should Atlas do instead?");
    const send = smallButton("ph:paper-plane-right Send", "Ask Atlas to do this instead", null, false);
    send.type = "submit";
    form.append(input, send);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const words = input.value.trim();
      if (!words) return input.focus();
      form.remove();
      sendChatMessage(words);
    });
    const wrap = document.createElement("div");
    wrap.className = "tool-consent-declined";
    wrap.append(done, form);
    card.replaceWith(wrap);
    input.focus();
    chatScrollToEnd();
  }

  async function drawToolConsent(card, event) {
    card.classList.add("tool-consent");
    const what = document.createElement("p");
    setLabel(what, `ph:hand Atlas wants to: ${event.label || event.name}`);
    card.appendChild(what);
    if (event.why) {
      const why = document.createElement("p");
      why.className = "muted tool-consent-why";
      why.textContent = `Because you asked: “${event.why}”`;
      card.appendChild(why);
    }
    const contentArea = document.createElement("div");
    const row = document.createElement("div");
    row.className = "row tool-consent-actions";
    card.append(contentArea, row);
    if (event.state === "expired") {
      contentArea.textContent = event.notice;
      delete card.dataset.pendingAct;
      return;
    }
    let suggestion = null;
    let inEditor = null;
    const allow = async (always) => {
      inEditor?.end();
      if (always) toolConsentAlways.add(toolConsentKey(event.name));
      const skip = suggestion ? [...suggestion.skipped] : [];
      for (const button of row.querySelectorAll("button")) button.disabled = true;
      try {
        const result = await apiJson("/chat/tools/execute", {
          method: "POST",
          body: JSON.stringify({ name: event.name, arguments: event.arguments, consent_id: event.consent_id || null, skip_hunks: skip }),
        });
        chatHistoryToSend.settle(card, event, "done");
        const said = always ? "ph:check-circle Allowed for this chat: " : "ph:check-circle ";
        //: A tool's label carries its own glyph; the chip leads with the tick, so the glyph goes.
        card.replaceWith(toolChip(`${said}${String(result.label || event.label || event.name).replace(/^ph:[\w-]+ /, "")}`));
        //: On the undo stack, its redo the call as it ran: the kept changes only, never the skipped ones.
        const ran = suggestion ? { ...event.arguments, content: suggestion.kept() } : event.arguments;
        if (inEditor) inEditor.saved(result, ran);
        else pushAgentChangeUndo({ undo: result.undo, label: result.label, tool: event.name }, { name: event.name, arguments: ran });
        refreshAfterToolChanges();
      } catch (error) {
        for (const button of row.querySelectorAll("button")) button.disabled = false;
        toast(error.message, true);
      }
    };
    const allowButton = smallButton("ph:check Allow", "Do this once", () => allow(false), false);
    row.appendChild(allowButton);
    //: Never for a removal: "always" there is how a chat bins twenty notes on one press.
    if (!event.removes) row.appendChild(smallButton("Allow always for this chat", "Do this, and changes like it in this chat, without asking", () => allow(true)));
    const decline = () => {
      inEditor?.end();
      chatHistoryToSend.settle(card, event, "cancelled");
      toolConsentInstead(card, event);
    };
    row.appendChild(smallButton("Decline", "Don't do this, and say what to do instead", decline));
    if (!event.removes && toolConsentAlways.has(toolConsentKey(event.name))) return allow(true);
    suggestion = await toolConsentSuggestion(event, contentArea).catch(() => null);
    if (suggestion) {
      suggestion.onChange = () => {
        const none = suggestion.skipped.size >= suggestion.hunks.length && suggestion.hunks.length > 0;
        allowButton.disabled = none;
        allowButton.title = none ? "Every change is skipped: decline it instead" : "Save the kept changes";
        inEditor?.refresh();
      };
      suggestion.onChange();
      inEditor = await toolConsentInEditor(event, suggestion, { onAccept: () => allow(false), onReject: decline }).catch(() => null);
      if (inEditor) contentArea.prepend(Object.assign(document.createElement("p"), { className: "muted tool-consent-head", textContent: "Also marked in the open document, to accept or reject there." }));
    }
    chatScrollToEnd();
  }

  Object.assign(window, { drawToolConsent });
})();
