// attach-accept.js: the one list of files a note or a chat message takes, and the work of a file
// pasted, dropped or picked into a note box (`handleFileUpload.run`), a file of its own so the
// boot scripts do not carry it: the chat input reads it when the Chat tab is built (wiring.js) and the
// capture card's staging reads it when the card opens (capture-card.js), in the app and on the desk.

//: **The one list of files a note or chat message takes**: chat's picker and the Quick
//: capture card's both read it (wiring.js sets the chat input's `accept`). `docview.VIEWABLE_SUFFIXES`
//: plus any image; `ATTACHMENT_SUFFIXES` takes all of it (tests/test_docview.py).
(() => {
  const ATTACH_ACCEPT = "image/*,.pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.odt,.rtf,.epub,.txt,.text,.log,.csv,.tsv,.md,.markdown,.html,.htm,.json,.xml,.yaml,.yml,.py,.js,.mjs,.cjs,.ts,.tsx,.jsx,.css,.scss,.java,.c,.h,.cpp,.hpp,.cs,.go,.rs,.rb,.php,.swift,.kt,.r,.sh,.bash,.zsh,.sql,.toml,.ini,.cfg,.diff,.patch,.vb,.vbs,.dockerfile,.mk";
  //: A file pasted, dropped or picked into a note box, from settings-wiring.js's `handleFileUpload`.
  handleFileUpload.run = async function (textarea, files) {
    // The capture composer is the one place that can stage: it is the only
    // textarea whose content becomes a note with an id a moment later. A
    // document's own editor writes into a document, which has no attachment
    // table, so it keeps the inline-markdown path for everything.
    const canStage = textarea.id === "entry-content";
    const images = canStage ? files.filter((f) => f.type.startsWith("image/")) : files;
    const others = canStage ? files.filter((f) => !f.type.startsWith("image/")) : [];
    if (others.length) {
      captureStagedFiles.push(...others);
      renderCaptureFiles();
      toast(
        others.length === 1
          ? `“${others[0].name}” will be attached when you save.`
          : `${others.length} files will be attached when you save.`
      );
    }
    if (!images.length) return;
    files = images;

    const cursorPosition = textarea.selectionStart;
    const selectionEnd = textarea.selectionEnd;
    const originalText = textarea.value;

    //: **The composer stages instead of uploading**, see `captureStagedImages`.
    //: Everywhere else (the document editor) still uploads inline, because a
    //: document has an id from the moment it exists and nothing to wait for.
    //:
    //: Written before the "Uploading…" placeholder below rather than after it:
    //: assigning `textarea.value` moves the selection, so a branch that ran
    //: afterwards and re-sliced against `selectionEnd` would cut the note in a
    //: different place than it meant to.
    if (canStage) {
      let inserted = "";
      for (const file of files) {
        const key = `img-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        captureStagedImages.push({
          key,
          file,
          objectUrl: URL.createObjectURL(file),
          name: file.name,
        });
        inserted += `![${file.name}](${stagedImageUrl(key)})\n`;
      }
      textarea.value =
        originalText.slice(0, cursorPosition) + inserted + originalText.slice(selectionEnd);
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      const at = cursorPosition + inserted.length;
      textarea.setSelectionRange(at, at);
      toast(
        files.length === 1
          ? `“${files[0].name}” will be saved with the note.`
          : `${files.length} images will be saved with the note.`,
      );
      return;
    }

    let textToInsert = "";
    for (const file of files) {
      textToInsert += `![Uploading ${file.name}…]()\n`;
    }
    textarea.value = originalText.substring(0, cursorPosition) + textToInsert + originalText.substring(selectionEnd);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));

    let added = 0;
    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await apiJson("/media/upload", {
          method: "POST",
          headers: authHeaders(),
          body: formData
        });
        // Image syntax (`![]()`) unconditionally became an <img> at render
        // time (renderInlineMarkdown): a non-image upload (PDF, docx, audio)
        // failed to decode as an image and the img.onerror handler then
        // reported it as "filename deleted", which is actively wrong: the
        // file uploaded fine and is sitting at res.url. Link syntax for
        // anything that isn't actually an image.
        const fileMarkdown = file.type.startsWith("image/")
          ? `![${res.filename}](${res.url})\n`
          : `[${res.filename}](${res.url})\n`;
        textarea.value = textarea.value.replace(`![Uploading ${file.name}…]()\n`, fileMarkdown);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        added += 1;
      } catch (err) {
        // Reported directly (§89 item 2): an upload failure rendered as if it
        // were the AI's own message: literal error text left sitting in the
        // note/document content, indistinguishable from something the user
        // actually typed. A toast is a notification; content is what gets
        // saved. Removing the placeholder outright (not replacing it with
        // more text) leaves the composer exactly as if the file were never
        // dropped/pasted, which is the honest description of what happened.
        console.error("Upload failed", err);
        textarea.value = textarea.value.replace(`![Uploading ${file.name}…]()\n`, "");
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        toast(err.message || `Couldn't upload "${file.name}".`, true);
      }
    }
    if (added) pushTextUndo("Added a file", textarea, originalText, textarea.value);
  };
  Object.assign(window, { ATTACH_ACCEPT });
})();
