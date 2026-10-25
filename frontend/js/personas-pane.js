// personas-pane.js: Settings, Personas (the built-in and custom persona list with inline edit), moved out of sheets-selects.js on 2026-10-12 for the boot gzip budget. Drawn when the pane opens and awaited or ignored by every caller: `LAZY_ENTRY_POINTS.personasPane` (app.js) stands in. `personaEditing`, `builtinPersonas` and `personaNamesNow` stay in sheets-selects.js.

async function savePersonaList(personas) {
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ personas }),
  });
  await renderPersonas();
  personaOptions();
}

async function renderPersonas() {
  //: The greeting picker is filled before the wait, not after it (the owner:
  //: "the dashboard greeting persona selection box is broken and there is no
  //: avatar next to it ... it sometimes works and sometimes doesnt"). It was
  //: filled at the end of this function, after `GET /preferences` and after
  //: the whole persona list was built, so on a busy server, or if anything in
  //: the list threw, the section showed an empty select and an empty face.
  renderDashboardPersonaSelect(personaNamesNow());
  const list = $("persona-list");
  showSkeletons(list, 3, "li");
  prefsCache = await apiJson("/preferences").catch(() => prefsCache);
  clearSkeletons(list);
  const custom = (prefsCache && prefsCache.personas) || [];
  const overrides = new Map(custom.map((p) => [p.name, p]));
  list.replaceChildren();

  const rows = [
    ...Object.keys(builtinPersonas()).map((name) => ({
      name,
      builtin: true,
      overridden: overrides.has(name),
      prompt: overrides.has(name) ? overrides.get(name).prompt : builtinPersonas()[name],
      //: Pre-filled from the built-in's own list, the same way `prompt`
      //: above is: editing and saving turns that pre-fill into a real
      //: override, exactly as editing the pre-filled prompt already does.
      thinkingWords: overrides.has(name)
        ? overrides.get(name).thinking_words || []
        : builtinThinkingWords()[name] || DEFAULT_THINKING_WORDS,
    })),
    ...custom
      .filter((p) => !(p.name in builtinPersonas()))
      .map((p) => ({ ...p, builtin: false, overridden: false, thinkingWords: p.thinking_words || [] })),
  ];

  renderDashboardPersonaSelect(rows.map((p) => p.name));

  for (const persona of rows) {
    const li = document.createElement("li");

    if (personaEditing === persona.name) {
      // Inline editor: prompt, thinking words, save/cancel.
      const textarea = document.createElement("textarea");
      textarea.rows = 3;
      textarea.value = persona.prompt;

      //: **Thinking words: one per line, the plain-text shape the backend
      //: itself stores them in** (`PersonaItem.thinking_words`), rather than
      //: comma-separated, since a phrase can itself contain a comma
      //: ("Reading, then re-reading" is a fine thinking word). Left empty
      //: means "use the default list, or this built-in's own", named in
      //: the hint below rather than guessed at from a blank box.
      const wordsLabel = document.createElement("label");
      wordsLabel.className = "persona-words-label";
      wordsLabel.textContent = "Thinking words (one per line, 8 to 40)";
      const wordsHint = document.createElement("p");
      wordsHint.className = "muted persona-words-hint";
      wordsHint.textContent =
        "Shown beside the thinking dots while this persona answers. Leave empty to use the default list.";
      const wordsBox = document.createElement("textarea");
      wordsBox.className = "persona-words-box";
      wordsBox.rows = 6;
      wordsBox.value = (persona.thinkingWords || []).join("\n");
      const wordsStatus = document.createElement("p");
      wordsStatus.className = "muted persona-words-status";

      const suggestBtn = smallButton(
        "Suggest with AI",
        "Ask the local model for about sixteen, in this persona's voice",
        async () => {
          suggestBtn.disabled = true;
          setLabel(wordsStatus, "ph:spin Asking the model…");
          try {
            const promptNow = textarea.value.trim() || persona.prompt;
            const reply = await apiJson("/personas/suggest-thinking-words", {
              method: "POST",
              body: JSON.stringify({ name: persona.name, prompt: promptNow }),
            });
            if (reply.thinking_words && reply.thinking_words.length) {
              wordsBox.value = reply.thinking_words.join("\n");
              wordsStatus.textContent = `${reply.thinking_words.length} suggested. Edit any of them, then Save.`;
            } else {
              wordsStatus.textContent = "The model didn't suggest any this time. Try again, or write your own.";
            }
          } catch (error) {
            wordsStatus.textContent = error.message || "Couldn't reach the model.";
          } finally {
            suggestBtn.disabled = false;
          }
        }
      );

      const row = document.createElement("div");
      row.className = "row";
      row.appendChild(
        smallButton(
          "Save",
          "",
          async () => {
            const prompt = textarea.value.trim();
            if (!prompt) return;
            const thinkingWords = wordsBox.value
              .split("\n")
              .map((w) => w.trim())
              .filter(Boolean);
            //: The backend's own rule (`PersonaItem._bounded_thinking_words`),
            //: checked here too so a mistake reads as one clear sentence
            //: beside the box instead of a raw 422 from a save that has
            //: already closed the editor.
            if (thinkingWords.length && (thinkingWords.length < 8 || thinkingWords.length > 40)) {
              wordsStatus.textContent = `${thinkingWords.length} words: use 8 to 40, or leave it empty for the default list.`;
              return;
            }
            const tooLong = thinkingWords.find((w) => w.length > 40);
            if (tooLong) {
              wordsStatus.textContent = `"${tooLong}" is longer than 40 characters.`;
              return;
            }
            //: Built from its code point, not typed literally: this file is
            //: itself swept for the character by `tests/test_no_em_dashes.py`.
            const emDash = String.fromCharCode(8212);
            const badWord = thinkingWords.find((w) => w.includes("!") || w.includes(emDash));
            if (badWord) {
              wordsStatus.textContent = `"${badWord}": no exclamation marks or em dashes.`;
              return;
            }
            const updated = custom.filter((p) => p.name !== persona.name);
            updated.push({ name: persona.name, prompt, thinking_words: thinkingWords });
            try {
              await savePersonaList(updated);
              personaEditing = null;
            } catch (error) {
              //: **Neither field is touched, and the editor stays open.**
              //: `renderPersonas()` (what `savePersonaList` calls on success)
              //: rebuilds this whole `<li>` from scratch, so calling it here
              //: too, on a failure, would throw away `textarea`/`wordsBox`
              //: and everything just typed into them along with the error
              //: it was meant to explain: a validation mistake would both
              //: fail to save and lose the edit. `personaEditing` was never
              //: cleared (only after `savePersonaList` succeeds, above), so
              //: nothing else that might re-render meanwhile mistakes this
              //: for a closed editor either.
              wordsStatus.textContent = error.message || "Couldn't save.";
            }
          },
          false
        )
      );
      row.appendChild(
        smallButton("Cancel", "", () => {
          personaEditing = null;
          renderPersonas();
        })
      );
      li.append(chip(persona.name), textarea, wordsLabel, wordsBox, wordsHint, suggestBtn, wordsStatus, row);
      list.appendChild(li);
      setTimeout(() => textarea.focus(), 0);
      continue;
    }

    const row = document.createElement("div");
    row.className = "entry-meta persona-row";
    //: Each persona its own mark, so a list of them is told apart at a
    //: glance; the app's own emblem for its own voice.
    const mark = document.createElement("span");
    mark.className = "persona-mark";
    //: 36px in the Settings list (the owner: "enlarge the avatar icons on
    //: personas in settings a bit"): a row there has the room, and a face
    //: at 20px was a coloured dot with a smile.
    fillPersonaMark(mark, persona.name, 36);
    row.append(mark, chip(persona.name, "item-title"));
    if (persona.builtin) {
      row.appendChild(chip(persona.overridden ? "Edited" : "Built-in", "item-label"));
    }
    const note = document.createElement("span");
    note.className = "muted persona-preview";
    note.textContent = persona.prompt;
    row.appendChild(note);

    const actions = document.createElement("span");
    actions.className = "entry-actions";
    actions.appendChild(
      smallButton("Edit", "Edit this persona's prompt", () => {
        personaEditing = persona.name;
        renderPersonas();
      })
    );
    if (persona.builtin && persona.overridden) {
      actions.appendChild(
        smallButton("Reset", "Restore the default prompt", async () => {
          await savePersonaList(custom.filter((p) => p.name !== persona.name));
        })
      );
    }
    if (!persona.builtin) {
      actions.appendChild(
        smallButton("Delete", "Remove this persona", async () => {
          if (!(await confirmDialog(`Delete the “${persona.name}” persona?`))) return;
          await savePersonaList(custom.filter((p) => p.name !== persona.name));
        })
      );
    }
    li.append(row, actions);
    list.appendChild(li);
  }
}

// A second, independent picker (asked for directly): the dashboard greeting
// otherwise always spoke in whichever persona Chat had active, with no way
// to give the notebook's own front page a different voice. "" means "no
// override" and falls back to active_persona server-side, same clear-with-
// empty-string convention display_name/dashboard_persona already share.
function renderDashboardPersonaSelect(names) {
  const select = $("dashboard-persona-select");
  const current = (prefsCache && prefsCache.dashboard_persona) || "";
  select.replaceChildren();
  const sameAsChat = document.createElement("option");
  sameAsChat.value = "";
  sameAsChat.textContent = "Same as Chat";
  select.appendChild(sameAsChat);
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  //: A saved name that is no longer in the list (the built-in was
  //: "Librarian" before it became Atlas; a custom persona can be deleted)
  //: left the select with no selected option, which the enhanced opener
  //: drew as an empty box with a chevron (the owner, 2026-09-14: "this
  //: dashboard welcome message persona dropdown box is broken visually").
  //: The old built-in reads as the new one; anything else unknown reads as
  //: "Same as Chat", which is what the server falls back to as well.
  const wanted = personaDisplayName(current) === current || current === "Librarian" ? personaDisplayName(current) : current;
  select.value = names.includes(wanted) ? wanted : "";
  paintDashboardPersonaMark();
}
