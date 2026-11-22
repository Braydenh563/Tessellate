// documents-check-ai.js: Check with AI and Check claims, in place (INBOX 410): the run's state, its findings against the text as it is now, the
// panel's status line, and the dictionary sheet's door. Moved out of documents.js and wrapped (L-documents-116): only what other files call goes
// on `window`. At load it only declares; documents.js's `renderDocTools` reads it at its own load.
(() => {
  // --- Check with AI, in place (INBOX 410) -----------------------------------
  //
  // The owner, 2026-09-24: "improve how the 'check with ai' feature works in the
  // documents editor." It used to leave the editor for the Chat tab, answer in a
  // bubble with nothing to apply, and raise a skill suggestion that did not fit
  // (INBOX 413). Now it stays: `POST /documents/{id}/ai-check` streams findings
  // (the exact words, a one-line reason, a one-line fix) and each becomes a
  // finding of kind `ai`, so it is underlined in the text, listed in the panel
  // under its own group, and answered by the same row and the same answers every
  // other finding has (`docFindingLine`, `docSuggestAnswers`), with Apply (the
  // row's check) and Dismiss. Stop is the button that started it. The model is
  // the documents feature's (Settings, Models, per feature).

  //: `state` is idle, running, done, stopped, offline or failed; `items` are
  //: `{text, message, replacement, near}` as they arrived, located afresh on every
  //: pass (`docAiFindings`) because the writer may keep typing while it runs.
  //: `mode` is "ai" or "claims" (Check claims against my notes, Phase G): the claim
  //: check puts its verdicts in the same `items`, each with a `claim` `{verdict, note}`.
  const docAiCheck = {
    state: "idle", items: [], message: "", controller: null, docId: null, mode: "ai",
    //: One request, no stream: the server writes nothing and answers every sentence.
    async claims() {
      if (docAiCheck.state === "running") return;
      const box = docSurface();
      const full = box?.text || "";
      if (!full.trim()) return toast("Nothing to check yet.", "info");
      const doc = currentDoc || (await ensureDocumentExists().catch(() => null));
      if (!doc) return toast("Nothing to check yet.", "info");
      Object.assign(docAiCheck, { state: "running", items: [], message: "", controller: null, docId: doc.id, mode: "claims" });
      $("doc-prose-panel")?.classList.remove("hidden");
      $("doc-prose")?.setAttribute("aria-expanded", "true");
      renderDocProse();
      try {
        const got = await apiJson(`/documents/${doc.id}/claim-check`, { method: "POST", body: JSON.stringify({ text: full }), readOnly: true });
        docAiCheck.items = got.claims.map((c) => ({
          text: c.text, message: c.message, replacement: "", near: c.start, claim: { verdict: c.verdict, note: c.note },
        }));
        docAiCheck.state = "done";
        docAiCheck.message = got.source === "words" ? "No AI model ran, so sentences were matched to notes by their words." : "";
      } catch (error) {
        docAiCheck.state = "failed";
        docAiCheck.message = error.message || "The check did not finish.";
      }
      renderDocProse();
    },
  };

  //: The streamed items as findings against the text as it is now. An item whose
  //: words are gone (applied, or edited away) is simply not drawn; one dismissed
  //: is gone from `items` itself.
  function docAiFindings(text) {
    if (!docAiCheck.items.length || docAiCheck.docId !== (currentDoc?.id ?? null)) return [];
    const out = [];
    for (const item of docAiCheck.items) {
      let start = text.indexOf(item.text, Math.max(0, item.near - 200));
      if (start === -1) start = text.indexOf(item.text);
      if (start === -1) continue;
      const finding = {
        rule: "ai",
        start,
        end: start + item.text.length,
        text: item.text,
        message: item.message,
        replacement: item.replacement || null,
        aiItem: item,
      };
      if (docProseIgnored.has(docProseKey(finding))) continue;
      out.push(finding);
    }
    return out;
  }

  function docAiDismiss(finding) {
    docAiCheck.items = docAiCheck.items.filter((item) => item !== finding.aiItem);
    renderDocProse();
  }


  //: **The check's own line in the panel**: what it is doing or did, and the
  //: two ways on (again, or Discuss in chat). No model is a `.notice-warn` with
  //: the way to connect one, rather than a toast that is gone before it is read.
  function docAiCheckStatus() {
    if (docAiCheck.state === "idle" || docAiCheck.docId !== (currentDoc?.id ?? null)) return null;
    const wrap = document.createElement("div");
    wrap.className = "doc-prose-ai";
    wrap.setAttribute("role", "status");
    const n = docAiCheck.items.length;
    const found = nounCount(n, "finding");
    if (docAiCheck.state === "offline") {
      const notice = document.createElement("p");
      notice.className = "notice notice-warn doc-prose-ai-notice";
      const icon = document.createElement("i");
      icon.className = "ph ph-plug";
      icon.setAttribute("aria-hidden", "true");
      const words = document.createElement("span");
      words.textContent = "No AI model is connected, so Check with AI cannot read this yet.";
      notice.append(icon, words);
      const open = smallButton("ph:gear Open Settings, Models", "Connect or choose the model documents use", () => {
        if (typeof openSettingsModal === "function") openSettingsModal("models");
      });
      open.classList.add("doc-prose-ai-settings");
      wrap.append(notice, open);
    } else {
      const line = document.createElement("span");
      line.className = "doc-prose-ai-line";
      if (docAiCheck.mode === "claims") {
        const marked = docAiCheck.items.filter((item) => item.claim.verdict !== "supported").length;
        line.textContent = docAiCheck.state === "running"
          ? "Checking sentences against your notes…"
          : docAiCheck.state === "failed"
            ? docAiCheck.message || "The check did not finish."
            : `${nounCount(n, "sentence")} checked, ${marked} not backed by a note.${docAiCheck.message ? ` ${docAiCheck.message}` : ""}`;
        if (docAiCheck.state === "failed") line.classList.add("error");
      } else if (docAiCheck.state === "running") {
        line.textContent = n ? `Checking with AI, ${found} so far…` : "Checking with AI…";
      } else if (docAiCheck.state === "stopped") {
        line.textContent = `Stopped. ${n ? `${found} before it stopped.` : "Nothing found before it stopped."}`;
      } else if (docAiCheck.state === "failed") {
        line.textContent = docAiCheck.message || "The check did not finish.";
        line.classList.add("error");
      } else {
        line.textContent = n ? `Checked with AI: ${found}.` : "Checked with AI: nothing to flag.";
      }
      wrap.appendChild(line);
    }
    const chat = smallButton("ph:chat-circle Discuss in chat", "Open this document in a chat, to ask about it in your own words", () => docAiDiscussInChat());
    chat.classList.add("doc-prose-ai-chat");
    wrap.appendChild(chat);
    return wrap;
  }


  //: **Managing the dictionary** (asked for by name): the sheet is documents-dictionary.js,
  //: fetched on the first press; the word list's reads stay here (`docDictionary`).
  async function openDocDictionary() {
    if (!(await lazyScript("/js/documents-dictionary.js"))) return toast("The dictionary could not be loaded.", true, { action: ["Try again", openDocDictionary] });
    return docDictionaryOpen();
  }

  //: The file's surface: what other files call.
  Object.assign(window, { docAiCheck, docAiFindings, docAiDismiss, docAiCheckStatus, openDocDictionary });
})();
