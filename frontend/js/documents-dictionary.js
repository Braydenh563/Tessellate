// documents-dictionary.js: the writing dictionary sheet (split out of documents.js, DOCUMENTS_PLAN L327).
//
// The dialog behind Prose check, Dictionary: the list of words, the field that finds and adds, import and export of a
// .txt file, and the sheet's other switches. **Loaded on the first press** (`openDocDictionary` in documents.js awaits
// `lazyScript`); the checker's own reads of the word list (`docDictionary`, `docDictionaryAdd`) stay in documents.js
// because every prose check uses them. Its top level wires the sheet's own controls, which exist in index.html by then.
(() => {
  //: The field finds and adds (`renderDocDictionary`, `docDictionaryAddTyped`);
  //: Add beside it is the same as Enter, for a pointer.
  $("doc-dictionary-add")?.addEventListener("click", () => docDictionaryAddTyped());
  $("doc-dictionary-search")?.addEventListener("input", () => renderDocDictionary());
  $("doc-dictionary-search")?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    docDictionaryAddTyped();
  });
  $("doc-dictionary-import")?.addEventListener("click", () => $("doc-dictionary-file")?.click());
  $("doc-dictionary-file")?.addEventListener("change", async (event) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    //: Cleared first, so choosing the same file again still raises a change.
    input.value = "";
    await docDictionaryImport(file);
  });
  $("doc-dictionary-export")?.addEventListener("click", () => docDictionaryExport());

  //: **Managing the dictionary.** Asked for by name. A list you can add to and
  //: never see again is a list nobody trusts, and a wrongly added word would
  //: otherwise silence a real typo forever with no way to find out why.
  //:
  //: **Redesigned as a settings sheet** (INBOX 410: "ugly and needs a proper
  //: professional modern redesign"). One field finds and adds: typing filters
  //: the list, Enter (or the field's Add) adds what is typed when it is not
  //: there already. The list is quiet rows whose remove shows on the row under
  //: the pointer or focus, with an empty state that says what the list is for
  //: and a no-match state that says Enter adds. The count is a fact by the
  //: title, in muted text rather than a boxed chip.
  async function docDictionaryOpen() {
    const dialog = $("doc-dictionary-dialog");
    if (!dialog) return;
    const search = $("doc-dictionary-search");
    if (search) search.value = "";
    renderDocDictionary();
    const variant = $("doc-spelling-variant");
    if (variant) variant.value = docSpellingVariant();
    extraNoticeMount($("xn-languagetool"), "languagetool", { fresh: true });
    const grammar = $("doc-grammar-check");
    if (grammar) {
      grammar.checked = !(prefsCache && prefsCache.grammar_check === false);
      //: A checker that failed to load says so where it is switched on, rather
      //: than sitting ticked over nothing.
      grammar.closest("label")?.setAttribute(
        "title",
        docGrammarError
          ? `The grammar checker could not start: ${docGrammarError}`
          : "Grammar and style rules, checked on this computer by Harper"
      );
    }
    const kindsOff = (prefsCache && prefsCache.prose_kinds_off) || [];
    $("doc-prose-groups")?.querySelectorAll("[data-prose-group]").forEach((box) => {
      box.checked = !kindsOff.includes(box.dataset.proseGroup);
    });
    const smart = $("doc-smart-punctuation");
    if (smart) smart.checked = !!(prefsCache && prefsCache.smart_punctuation === true);
    const linkOffers = $("doc-link-offers");
    if (linkOffers) linkOffers.checked = docLinkOfferEnabled();
    const linkText = $("doc-check-link-text");
    if (linkText) linkText.checked = docCheckLinkText();
    if (!dialog.open) dialog.showModal();
    search?.focus();
  }

  //: The words matching the field, and the list drawn from them. Called on
  //: open, on every keystroke in the field, and after every add or remove.
  function renderDocDictionary() {
    const list = $("doc-dictionary-list");
    if (!list) return;
    const words = [...docDictionary()].sort((a, b) => a.localeCompare(b));
    const query = ($("doc-dictionary-search")?.value || "").trim().toLowerCase();
    const shown = query ? words.filter((word) => word.includes(query)) : words;
    const count = $("doc-dictionary-count");
    if (count) {
      count.textContent = words.length ? nounCount(words.length, "word") : "";
    }
    //: Add is offered only when there is something new to add: a word typed
    //: that is not already in the list.
    const add = $("doc-dictionary-add");
    if (add) {
      const addable = !!query && !docDictionary().has(query) && docDictionaryWordOk(query);
      add.hidden = !addable;
      if (addable) setLabel(add, `ph:plus Add “${query}”`);
    }
    list.replaceChildren();
    if (!shown.length) {
      const empty = document.createElement("li");
      empty.className = "empty-state doc-dictionary-empty";
      empty.textContent = query
        ? docDictionary().has(query)
          ? ""
          : `No word here matches “${query}”. Press Enter to add it.`
        : "No words yet. Type one above and press Enter, or add one from a flagged word.";
      if (empty.textContent) list.appendChild(empty);
      return;
    }
    for (const word of shown) {
      const row = document.createElement("li");
      row.className = "doc-dictionary-row";
      const label = document.createElement("span");
      label.className = "doc-dictionary-word";
      label.textContent = word;
      const remove = smallButton("ph:x", `Remove “${word}”`, async () => {
        await docDictionaryWrite([...docDictionary()].filter((other) => other !== word));
        renderDocDictionary();
        renderDocProse();
        $("doc-dictionary-search")?.focus();
      });
      remove.classList.add("icon-only", "doc-dictionary-remove");
      remove.setAttribute("aria-label", `Remove “${word}”`);
      row.append(label, remove);
      list.appendChild(row);
    }
  }

  //: A dictionary entry is one word as the checker reads words: letters, with
  //: an apostrophe or a hyphen inside. Anything else would never match a
  //: finding, so it would sit in the list doing nothing.
  function docDictionaryWordOk(word) {
    return /^[\p{L}][\p{L}\p{N}'’-]{0,59}$/u.test(word);
  }

  async function docDictionaryAddTyped() {
    const search = $("doc-dictionary-search");
    const word = (search?.value || "").trim();
    if (!word) return;
    if (!docDictionaryWordOk(word)) return toast("One word at a time: letters, with an apostrophe or hyphen inside.", "info");
    if (!docDictionary().has(word.toLowerCase())) await docDictionaryAdd(word);
    if (search) search.value = "";
    renderDocDictionary();
    renderDocProse();
    search?.focus();
  }

  //: **In and out as a .txt file, one word per line.** Import adds and never
  //: removes: a file from another machine merged into this one is the common
  //: case, and replacing would silently drop every word only this one had.
  async function docDictionaryImport(file) {
    if (!file) return;
    const text = await file.text().catch(() => "");
    const incoming = [...new Set(text.split(/[\r\n,;\t]+/).map((w) => w.trim().toLowerCase()).filter(docDictionaryWordOk))];
    const have = docDictionary();
    const fresh = incoming.filter((word) => !have.has(word));
    if (!incoming.length) return toast("No words found in that file. One word per line.", "info");
    if (fresh.length) await docDictionaryWrite([...have, ...fresh]);
    renderDocDictionary();
    renderDocProse();
    toast(fresh.length
      ? `Added ${nounCount(fresh.length, "word")}${incoming.length > fresh.length ? `; ${incoming.length - fresh.length} were already here` : ""}.`
      : "Every word in that file is already here.");
  }

  function docDictionaryExport() {
    const words = [...docDictionary()].sort((a, b) => a.localeCompare(b));
    if (!words.length) return toast("The dictionary is empty, so there is nothing to export.", "info");
    //: Through `saveFile`, so the desktop window (which swallows an anchor's
    //: download) saves it too (audit FE-16).
    return saveFile("writing-dictionary.txt", new Blob([`${words.join("\n")}\n`], { type: "text/plain" }));
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { docDictionaryOpen });
})();
