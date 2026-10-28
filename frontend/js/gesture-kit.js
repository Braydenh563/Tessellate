// Gesture-only chat panels, moved out of the boot scripts on 2026-10-26 for the
// gzip budget (tests/test_static_compression.py): the active-model badge's
// spec panel (from ai-tools.js), editing an answer in place (from
// sheets-selects.js) and a note's "Explain this note" menu row (from menus.js).
// Each is reached only by a click, and no caller reads a return value, so
// `LAZY_ENTRY_POINTS`-style stand-ins (`gestureKit`, lazy-entries.js) fetch
// this file on first use and then call the real function.

async function openChatModelPanel() {
  const name = modelStatus && modelStatus.chat_model;
  const panel = $("chat-model-panel");
  if (!panel || !name) return;
  panel.replaceChildren();
  const head = document.createElement("div");
  head.className = "row space-between chat-model-panel-head";
  const title = document.createElement("strong");
  title.textContent = name;
  title.className = "chat-model-panel-name";
  head.appendChild(title);
  const close = smallButton("ph:x", "Close", () => panel.classList.add("hidden"));
  close.classList.add("icon-only");
  head.appendChild(close);
  panel.appendChild(head);

  const list = document.createElement("dl");
  list.className = "chat-model-facts";
  const loading = document.createElement("p");
  loading.className = "muted";
  setLabel(loading, "ph:spin Reading the model's own specification…");
  panel.append(list, loading);
  panel.classList.remove("hidden");
  placeChatModelPanel();

  const spec = await apiJson(`/models/spec?name=${encodeURIComponent(name)}`).catch(() => null);
  //: The panel was measured empty a moment ago; it is a different height now.
  placeChatModelPanel();
  loading.remove();
  if (!spec) {
    const failed = document.createElement("p");
    failed.className = "muted";
    //: Named as a *backend* silence rather than a model fault: the usual cause
    //: is that Ollama is not running, and "unknown" with no reason sends
    //: people looking at the wrong thing.
    failed.textContent =
      "The backend didn't answer. This needs the model runner to be up, everything else in this panel comes from it.";
    panel.appendChild(failed);
    return;
  }
  const fact = (label, value, why) => {
    if (value === null || value === undefined || value === "") return;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    if (why) dd.title = why;
    list.append(dt, dd);
  };
  fact("Family", spec.family, "The architecture this model is built on");
  fact("Size", spec.parameters, "How many parameters it has");
  fact("Quantisation", spec.quantisation, "How much its weights were compressed to fit in memory");
  if (spec.context_length) {
    fact(
      "Declared window",
      `${compactTokens(spec.context_length)} tokens`,
      "What the model says it can hold"
    );
  }
  if (spec.usable_context) {
    fact(
      "Used here",
      `${compactTokens(spec.usable_context)} tokens`,
      "What this app actually runs it at, often lower on purpose, to leave room for the key/value cache"
    );
  }
  //: Tri-state, and rendered as three states. `null` means this backend does
  //: not say, and drawing that as "No" would be a confident lie about a model
  //: that works fine: the endpoint's own docstring makes the same point.
  const flag = (value) => (value === null || value === undefined ? "Not reported" : value ? "Yes" : "No");
  fact("Can call tools", flag(spec.supports_tools), "Whether agent mode can work with this model");
  fact("Can show its reasoning", flag(spec.supports_thinking));
  fact("Can see images", flag(spec.supports_vision), "Whether it can read a picture or a scanned page");

  const change = smallButton("ph:gear Change the model", "Open Settings → Models", () => {
    panel.classList.add("hidden");
    openSettingsModal("models", "chat-model-select");
  });
  panel.appendChild(change);
}

// Editing questions has worked for a while; answers were fixed forever, so a
// model that got one detail wrong left you regenerating the whole thing and
// hoping. Editing in place keeps the rest of the thread intact.
function editChatAnswer(handles, turnIndex, current) {
  if (handles.bubble.querySelector(".answer-editor")) return; // already open
  const editor = document.createElement("div");
  editor.className = "answer-editor";
  const box = document.createElement("textarea");
  box.value = current;
  box.rows = Math.min(20, Math.max(4, current.split("\n").length + 1));
  box.setAttribute("aria-label", "Edit this answer");

  const target = handles.timeline.answerElement();
  const finish = (markdown) => {
    editor.remove();
    target.classList.remove("hidden");
    if (markdown !== null) handles.timeline.replaceAnswer(markdown);
  };

  const save = document.createElement("button");
  save.className = "small";
  save.type = "button";
  save.textContent = "Save";
  save.addEventListener("click", async () => {
    const next = box.value.trim();
    if (!next) {
      toast("An empty answer isn't a correction: delete the message instead.", "info");
      return;
    }
    if (chatConv.id) {
      const priorAnswer = chatConv.turns[turnIndex]?.answer;
      const chatId = chatConv.id;
      try {
        await apiJson(`/conversations/${chatConv.id}/turns/${turnIndex}/answer`, {
          method: "PUT",
          body: JSON.stringify({ content: next }),
        });
      } catch (error) {
        toast(error.message, true);
        return; // leave the editor open rather than losing the edit
      }
      if (priorAnswer != null) {
        pushRequestUndo(
          "Edited an answer",
          `/conversations/${chatId}/turns/${turnIndex}/answer`,
          "PUT",
          { content: priorAnswer },
          { content: next },
          () => (chatConv?.id === chatId ? openConversation(chatId) : null)
        );
      }
    }
    if (chatConv.turns[turnIndex]) chatConv.turns[turnIndex].answer = next;
    finish(next);
    if (!handles.bubble.querySelector(".edited-marker")) {
      handles.bubble.insertBefore(
        editedMarker(),
        handles.bubble.querySelector(".msg-actions")
      );
    }
    toast("Answer updated.");
  });

  const cancel = document.createElement("button");
  cancel.className = "ghost small";
  cancel.type = "button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => finish(null));

  const row = document.createElement("div");
  row.className = "row";
  row.append(save, cancel);
  editor.append(box, row);
  target.classList.add("hidden");
  target.after(editor);
  box.focus();
}

//: **Explain this note** (WORLD_CLASS_PLAN section 17 row 6, from the owner's
//: first notes: "the AI reads answers aloud; explains what you entered"). The
//: note's words, then each note it links to with the reason the link carries,
//: read with the browser's own voices (`speakText`, which a second press stops)
//: and shown in a sheet as it is read. From the links' reasons, so it works
//: with the model off; a link nobody gave a reason says so.
async function explainNote(entry) {
  const full = await apiJson(`/entries/${entry.id}`).catch(() => null);
  if (!full) return toast("Couldn't read this note.", true, { action: ["Try again", () => explainNote(entry)] });
  const words = stripFrontmatter(full.content || "").replace(/^#+\s*/gm, "").trim();
  const links = full.links || [];
  const name = (link) => noteNamePlain(link.preview).slice(0, 80) || "a note";
  const lines = links.map((link) => `“${name(link)}”: ${link.reason ? link.reason : "no reason was given for this link"}.`);
  const about = links.length
    ? `It links to ${nounCount(links.length, "note")}. ${lines.join(" ")}`
    : "It links to no other notes yet.";
  speakText(`${words}\n\n${about}`);
  openSheet({
    label: "Explain this note",
    name: "explain-note",
    onClose: () => {
      if ("speechSynthesis" in window) speechSynthesis.cancel();
    },
    build: (card) => {
      const body = document.createElement("div");
      body.className = "explain-note-body";
      const text = document.createElement("p");
      text.className = "explain-note-text";
      text.textContent = words || "This note has no words of its own.";
      const head = document.createElement("p");
      head.className = "muted text-sm";
      head.textContent = links.length ? `It links to ${nounCount(links.length, "note")}:` : "It links to no other notes yet.";
      body.append(text, head);
      if (links.length) {
        const list = document.createElement("ul");
        list.className = "explain-note-links";
        for (const [i, link] of links.entries()) {
          const li = document.createElement("li");
          li.textContent = lines[i];
          list.appendChild(li);
        }
        body.appendChild(list);
      }
      const again = smallButton("ph:speaker-high Read again", "Read it aloud again, or stop", () => speakText(`${words}\n\n${about}`));
      body.appendChild(again);
      card.appendChild(body);
    },
  });
}
