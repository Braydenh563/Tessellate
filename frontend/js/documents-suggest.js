// documents-suggest.js: what a click on a flagged word or a press on "Check with AI" runs (split out of documents.js,
// DOCUMENTS_PLAN L327).
//
// The popup that opens on a flagged word, the translate hand-off, "Discuss in chat", and the in-place AI review.
// **Loaded on the first use**: documents.js keeps a stand-in with each name below that fetches this file and then
// calls the real function, which has replaced the stand-in by then (a window property, so the name resolves anew).
// What the popup is made of (`docSuggestAnswers`, `docFindingAnswerRows`) is here too; the prose panel's rows and the
// suggestion menu await the stand-ins in documents.js. `placeDocSuggest` and the word list's rules stay there.
(() => {
  function openDocSuggest(finding, anchorRect, focus = true) {
    const menu = $("doc-suggest-menu");
    if (!menu) return;
    //: The last guard before the origin: a rect with nothing in it is asked of
    //: the finding again, and with no answer the menu does not open rather
    //: than opening at `8,8` (INBOX 421 c).
    if (!docRectUsable(anchorRect)) anchorRect = docFindingAnchor(finding, null);
    if (!docRectUsable(anchorRect)) return;
    docSuggestOpenFor = finding;
    menu.replaceChildren();

    const head = document.createElement("div");
    head.className = "doc-suggest-head";
    head.appendChild(docFindingLine(finding, "head"));
    menu.appendChild(head);
    menu.appendChild(
      docSuggestAnswers(finding, {
        close: closeDocSuggest,
        current: () => docSuggestOpenFor === finding,
        reflow: placeDocSuggest,
      })
    );

    docLiftToViewport(menu);
    menu.classList.remove("hidden");
    //: Copied rather than kept by reference, and with a right edge filled in:
    //: `DOMRect`s are live for some sources and stale for others, and the caret
    //: fallback hands over a point with no `right` at all, which the
    //: right-alignment below would otherwise read as NaN and place nowhere.
    docSuggestAnchor = {
      left: anchorRect.left,
      right: anchorRect.right ?? anchorRect.left,
      top: anchorRect.top,
      bottom: anchorRect.bottom,
    };
    placeDocSuggest();
    //: Only when the gesture asked for the menu. A plain click on a word is
    //: someone putting the caret in it, and taking the focus then sends their
    //: next keystroke to a button (see the `click` listener below).
    if (focus) menu.querySelector("button")?.focus();
  }

  //: A passage, translated by the offline translator (the "Translate this" sheet) when its package is
  //: installed; otherwise a language and the local model, asked in the chat so the answer is somewhere
  //: you can read, keep or ignore.
  async function docTranslatePassage(text) {
    const status = await apiJson("/translate/status", { silent: true }).catch(() => null);
    if (status?.installed && status.pairs?.length) {
      await ensureModule("translate");
      return translateCaught({ selection: text });
    }
    const language = await promptDialog(
      "Translate this passage into which language?",
      docLastTranslateLanguage || "French"
    );
    if (!language) return;
    docLastTranslateLanguage = language;
    const box = document.getElementById("chat-input");
    if (!box) return toast("The chat isn't available right now.", "info");
    switchTab("chat");
    box.value = `Translate this into ${language}, and keep the formatting:\n\n${text}`;
    box.focus();
    box.dispatchEvent(new Event("input", { bubbles: true }));
  }

  //: **The request the rules above cannot answer.** Handed to the chat rather
  //: than run silently, for the reason `docProseHeader`'s own comment gives:
  //: judging meaning takes real inference time, and this editor's whole
  //: character-count/word-goal/completion stack is built on being instant. A
  //: background pass that occasionally froze the UI for a few seconds mid-word
  //: would be a worse editor than one with no AI review at all.
  //:
  //: Asks for a list rather than a rewrite, the same reason `docProseFix`
  //: never silently replaces text without the exact span matching first: an
  //: editor that hands your document to a model and gets a different document
  //: back, with no way to see what changed or why, is not reviewing your
  //: writing, it is overwriting it. A list of numbered issues, each with what
  //: is wrong and one suggested fix, is a thing you can read, agree or
  //: disagree with, and apply by hand, same shape as everything else this
  //: checker offers.
  //: **A badge, not a wall of text.** Asked for directly: "the 'check with ai'
  //: button in the documents should attach a link to the document or an excerpt
  //: from the document to read but in a little attached badge that can be
  //: removed so the document text isnt just pasted below."
  //:
  //: This used to write the whole document into the composer. Three things were
  //: wrong with that and the report names the first: the question you are about
  //: to ask is buried under six thousand characters you did not type, so the
  //: composer stops being somewhere you can write. The second is that there was
  //: no way to change your mind, the text was *in* the box, so unattaching it
  //: meant finding where the prompt ended and the document began. The third is
  //: that it sends a snapshot: the model reads whatever the document said at the
  //: moment the button was pressed, not what it says when the question is
  //: actually asked.
  //:
  //: `attachedDocuments` fixes all three and it already existed, the composer
  //: has staged documents as removable chips since files could be dropped into
  //: chat, and `sendChat` already passes their ids to the backend, which reads
  //: them itself. So this attaches rather than pastes, and the composer is left
  //: holding one short sentence: the question.
  //:
  //: A *selection* is the one case that still travels as text. It is short by
  //: definition, it is the passage the question is about, and there is nothing
  //: in the document's id to say which part of it was meant.
  const DOC_AI_REVIEW_SELECTION_CHARS = 1200;

  //: **Discuss in chat, the secondary way now** (INBOX 410). Everything above
  //: about the badge still holds; what changed is the prompt. The long ask that
  //: used to go with it ("Read this for the things a spellchecker can't
  //: catch...") shared enough words with a proofreading skill to raise "You have
  //: a skill for this" over the composer, which the owner reported as not
  //: accurate (INBOX 413). The check itself runs in place now (`docAiReview`),
  //: so this opens the conversation and leaves the question to the writer: the
  //: document as a chip, a selection as a quote, and nothing else typed for them.
  function docAiDiscussInChat() {
    const box = docSurface();
    const text = (box?.text || "").trim();
    if (!text) return toast("Nothing to discuss yet.", "info");
    const input = document.getElementById("chat-input");
    if (!input) return toast("The chat isn't available right now.", "info");
    const range = box ? box.selection() : null;
    const selection = range ? box.text.slice(range.from, range.to).trim() : "";
    switchTab("chat");
    if (selection) {
      const quoted =
        selection.length > DOC_AI_REVIEW_SELECTION_CHARS
          ? `${selection.slice(0, DOC_AI_REVIEW_SELECTION_CHARS)}…`
          : selection;
      input.value = `${quoted.split("\n").map((line) => `> ${line}`).join("\n")}\n\n`;
    } else {
      const attached = attachDocumentToChat(currentDoc && currentDoc.id, (currentDoc && currentDoc.title) || $("doc-title")?.value || "This document");
      if (!attached) {
        //: The one case where pasting is still the honest answer: the chip
        //: cannot be added (four already staged, or an unsaved document with no
        //: id yet), and silently asking about nothing would be worse.
        input.value = `${text.slice(0, 6000)}${text.length > 6000 ? "…" : ""}\n\n`;
      }
    }
    input.focus();
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }


  async function docAiReview() {
    if (docAiCheck.state === "running") {
      docAiCheck.controller?.abort();
      return;
    }
    const box = docSurface();
    const full = box?.text || "";
    if (!full.trim()) return toast("Nothing to check yet.", "info");
    const doc = currentDoc || (await ensureDocumentExists().catch(() => null));
    if (!doc) return toast("Nothing to check yet.", "info");
    const range = box.selection();
    const selection = range.to > range.from ? full.slice(range.from, range.to) : "";
    const controller = new AbortController();
    Object.assign(docAiCheck, {
      state: "running", items: [], message: "", controller, docId: doc.id, mode: "ai",
    });
    //: The panel opens on the check, so the findings land where the writer
    //: can see them arrive.
    $("doc-prose-panel")?.classList.remove("hidden");
    $("doc-prose")?.setAttribute("aria-expanded", "true");
    renderDocProse();
    const offset = selection ? range.from : 0;
    try {
      // `api.stream` (F5): 401 and refusals are thrown as they were here.
      const response = await api.stream(`/documents/${doc.id}/ai-check`, {
        method: "POST",
        //: The text as it is on screen, not as last saved: the autosave is a
        //: second behind the typing, and a finding about words that are no
        //: longer there is one the panel cannot find.
        body: JSON.stringify({ selection: selection || full }),
        // A check is a read: it must not empty the app's read cache.
        readOnly: true,
        signal: controller.signal,
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffered = "";
      const onEvent = (event) => {
        if (event.type === "item") {
          docAiCheck.items.push({
            text: event.quote,
            message: event.reason,
            replacement: event.fix || "",
            near: offset + Math.max(0, (selection || full).indexOf(event.quote)),
          });
          renderDocProse();
        } else if (event.type === "done") {
          docAiCheck.state = event.stopped ? "stopped" : event.ollama_running === false ? "offline" : event.message ? "failed" : "done";
          docAiCheck.message = event.message || "";
        }
      };
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffered += decoder.decode(value, { stream: true });
        const lines = buffered.split("\n");
        buffered = lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            onEvent(JSON.parse(line));
          } catch {
            recordBrowserLog("WARN", [`[AI check] Unparseable line: ${line.slice(0, 80)}`]);
          }
        }
      }
      if (docAiCheck.state === "running") docAiCheck.state = "done";
    } catch (error) {
      if (error.name === "AbortError") {
        docAiCheck.state = "stopped";
      } else {
        docAiCheck.state = "failed";
        docAiCheck.message = error.message || "The check did not finish.";
      }
    } finally {
      if (docAiCheck.controller === controller) docAiCheck.controller = null;
      renderDocProse();
    }
  }

  //: **The answers to a finding as data** (INBOX 689): the candidates that
  //: replace the word, then "Add to dictionary" (a spelling or a variant) and
  //: "Ignore in this document". `docSuggestAnswers` draws them as buttons in
  //: the popover and the panel row, and a suggested change that carries a
  //: finding lists the same rows in its own menu (`docSuggestMenu`), so the
  //: three can never offer different things. Each row's `run(close)` does the
  //: whole job, calling `close` in the order the surface needs: after a fix,
  //: before the dictionary write and the ignore.
  function docFindingAnswerRows(finding) {
    const rows = docSuggestAlternatives(finding).map((option, index) => {
      const removal = `Remove \u201c${finding.text}\u201d`;
      return {
        kind: "candidate",
        best: index === 0,
        label: option === " " ? "one space" : option === "" ? removal : option,
        title: option === "" ? removal : `Replace with \u201c${option}\u201d`,
        run: (close = () => {}) => {
          docProseFix({ ...finding, replacement: option });
          close();
        },
      };
    });
    if (finding.rule === "spelling" || finding.rule === "variant") {
      rows.push(docSpell.dictionaryRow(finding.text));
    }
    rows.push({
      kind: "action",
      id: "ignore",
      label: `ph:eye-slash ${docIgnoreLabel(finding)}`,
      title: finding.rule === "link-offer"
        ? "Never offer a link to this name, in any document"
        : "Stop flagging this wording in this document until Tessellate is restarted",
      run: (close = () => {}) => {
        close();
        docProseIgnore(finding);
      },
    });
    return rows;
  }

  //: **The answers to a finding, built once and drawn in two places**
  //: (DOCUMENTS_PLAN 12 D2 and D3): the floating menu over the word, and the
  //: expanded row in the panel. They were two code paths offering the same four
  //: things, which is how the panel ended up with no answers of its own and had
  //: to open the menu over the text to have any.
  //:
  //: `close` dismisses whichever surface this was drawn into, `current` says
  //: whether that surface is still showing this finding (the AI round-trip takes
  //: seconds and the reader may have moved on), and `reflow` lets a surface that
  //: positions itself do so again after the answers change size.
  function docSuggestAnswers(finding, opts = {}) {
    const close = opts.close || (() => {});
    const current = opts.current || (() => true);
    const reflow = opts.reflow || (() => {});
    const inline = opts.inline === true;
    const frag = document.createDocumentFragment();

    const list = document.createElement("div");
    list.className = inline ? "doc-suggest-list doc-suggest-list-inline" : "doc-suggest-list";
    //: **A candidate word is a word, not an action, and it used to be drawn as
    //: one.** Every row carried the same `ph:check`, so five suggestions read as
    //: five identical commands with different arguments, and the eye had nothing
    //: to tell them apart by except the text it was meant to be comparing.
    //: Reported as exactly that. Every other spell checker anyone has used shows
    //: the candidates bare, and that is the point: the row IS the word. The
    //: check mark stays where it means something, on the panel's own "apply this
    //: fix" button, and the actions below this list keep their icons, so the
    //: menu now separates into "which word" and "what to do about it" without a
    //: divider having to say so. The first candidate carries the weight, because
    //: it is the one Enter and a double-click take.
    const answerRows = docFindingAnswerRows(finding);
    answerRows.filter((row) => row.kind === "candidate").forEach((row) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = row.best ? "doc-suggest-item doc-suggest-best" : "doc-suggest-item";
      item.textContent = row.label;
      item.title = row.title;
      item.addEventListener("click", () => row.run(close));
      list.appendChild(item);
    });
    if (!answerRows.some((row) => row.kind === "candidate")) {
      const none = document.createElement("p");
      none.className = "muted doc-suggest-none";
      //: A rule with no fix still opens this menu, because "ignore it" and "this
      //: is fine" are answers too: and because a row you cannot press at all
      //: reads as a broken row.
      none.textContent = "No single answer for this one, it is a place to look, not a correction.";
      list.appendChild(none);
    }
    frag.appendChild(list);

    const actions = document.createElement("div");
    actions.className = inline ? "doc-suggest-actions doc-suggest-actions-inline" : "doc-suggest-actions";
    for (const row of answerRows.filter((other) => other.kind === "action")) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "doc-suggest-item";
      setLabel(button, row.label);
      button.title = row.title;
      button.addEventListener("click", () => row.run(close));
      actions.appendChild(button);
    }

    if (docFindingIsPassage(finding)) {
      //: **"Ask the AI for wordings", where the app itself has no answer.** Asked
      //: for directly: "the listed errors in suggestions have no way to have the
      //: ai write a suggested replacement or multiple for the user to choose."
      //:
      //: A row rather than an automatic call: this costs a model round-trip of
      //: several seconds, and firing one every time a menu opens would make the
      //: menu feel broken on a small local model. It replaces itself with the
      //: options when they arrive, so the menu that asked is the menu that
      //: answers: pressing an option applies it exactly as a built-in fix does,
      //: through `docProseFix`, which re-checks the document before writing.
      const askAi = document.createElement("button");
      askAi.type = "button";
      askAi.className = "doc-suggest-item doc-suggest-ai";
      setLabel(askAi, "ph:sparkle Ask Atlas for wordings\u2026");
      askAi.title = "Have the local model suggest two or three other ways to put this";
      askAi.addEventListener("click", async () => {
        if (!currentDoc || !currentDoc.id) return toast("Save the document first.", "info");
        setLabel(askAi, "ph:hourglass Thinking\u2026");
        askAi.disabled = true;
        const body = await apiJson(`/documents/${currentDoc.id}/rephrase`, {
          method: "POST",
          body: JSON.stringify({ passage: finding.text, note: finding.message || "" }),
        }).catch(() => null);
        //: The surface may have been closed, or opened on something else, while
        //: the model was thinking. Writing into it then would put one finding's
        //: suggestions under another finding's heading.
        if (!current()) return;
        const options = (body && body.options) || [];
        if (!options.length) {
          setLabel(askAi, "ph:sparkle Ask Atlas for wordings\u2026");
          askAi.disabled = false;
          return toast(
            (body && body.message) || "No other wordings came back for that one.",
            "info"
          );
        }
        askAi.remove();
        for (const option of options) {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "doc-suggest-item doc-suggest-ai-option";
          setLabel(item, `ph:sparkle ${option}`);
          item.title = `Replace with \u201c${option}\u201d`;
          item.addEventListener("click", () => {
            docProseFix({ ...finding, replacement: option });
            close();
          });
          list.appendChild(item);
        }
        reflow();
      });
      actions.appendChild(askAi);

      //: **Translation: the offline translator when it is installed, else the chat.**
      //: Without the package the honest offer is the local model, with the question
      //: already written, where the answer is visible and correctable, not a silent
      //: rewrite of the document with something nobody checked.
      const translate = document.createElement("button");
      translate.type = "button";
      translate.className = "doc-suggest-item";
      setLabel(translate, "ph:translate Translate this passage\u2026");
      translate.addEventListener("click", () => {
        close();
        docTranslatePassage(finding.text);
      });
      actions.appendChild(translate);
    }
    frag.appendChild(actions);
    return frag;
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  //: One name in the shared scope: documents.js keeps a stand-in per function
  //: (same name), which calls through this once the file is in.
  Object.assign(window, { docSuggestPiece: { openDocSuggest, docTranslatePassage, docAiDiscussInChat, docAiReview, docFindingAnswerRows, docSuggestAnswers } });
})();
