// status-panels.js: the search engine health rows, the backend picker, the undo history menu and Email support report, moved out of status.js on 2026-10-12 for the boot gzip budget. Each is called for its effect: `lazy-entries.js` stands in until this loads.

//: **A report by email, with the bundle saved first** (INBOX 256, the owner:
//: "suggest that they download the support bundle and send it to my email
//: ... even open the email dialogue for them"). The bundle is a download,
//: never an attachment a page can add itself, so the order is: save it,
//: then open the person's mail app on a message that names the file to
//: attach. The address is also put on the clipboard, because a webview
//: without a mail handler opens nothing and says nothing.
async function emailSupportReport(about) {
  await downloadSupportBundle();
  //: The version is read off the page's own stamped script URL, the one
  //: thing every build carries without another request.
  const stamp = (document.querySelector('script[src*="app.js?v="]')?.getAttribute("src") || "").split("?v=")[1] || "";
  const subject = encodeURIComponent(`Tessellate report${stamp ? ` (${stamp.split("-")[0]})` : ""}`);
  const body = encodeURIComponent(
    (about ? `What happened: ${about}\n\n` : "What happened: \n\n") +
      "Please attach tessellate-support-bundle.zip, which was just saved to your downloads.\n"
  );
  try {
    await navigator.clipboard?.writeText?.(SUPPORT_EMAIL);
  } catch {
    // no clipboard in this context: the address is in the toast below
  }
  const link = document.createElement("a");
  link.href = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  toast(`Your mail app should open. The address, ${SUPPORT_EMAIL}, is on your clipboard too.`);
}

//: **The stack you can see.** Reported: the global undo is "significantly
//: outdated and dont register a lot of actions", and the second half of that
//: is that there was no way to *look*. A single button that says "Undo: moved
//: a note to the bin" tells you the last thing and nothing about the four
//: before it, so undoing three steps is three presses into the dark.
//:
//: Right-click, the same gesture the back/forward pair already uses for their
//: own history, and named in the tooltip so it is discoverable rather than
//: folklore. Picking a row undoes everything down to and including it, which
//: is what a history list means everywhere else.
function openUndoHistoryMenu(anchorEl) {
  const menu = $("undo-history-menu");
  if (!menu) return;
  menu.replaceChildren();
  if (!undoStack.length) return;
  const list = document.createElement("ul");
  list.className = "action-menu-list";
  //: Newest first, because the newest is the one you are almost always
  //: reaching for and a list you have to read upwards is a list you misread.
  [...undoStack].reverse().forEach((action, offset) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "action-menu-item";
    setLabel(button, `ph:arrow-u-up-left ${action.label}`);
    button.title = offset === 0 ? "Undo this" : `Undo this and the ${offset} after it`;
    button.addEventListener("click", async () => {
      menu.classList.add("hidden");
      //: One at a time through `performUndo`, so a step that fails stops the
      //: run with the stack intact rather than leaving the notebook half
      //: rolled back: the same contract a single press already has.
      for (let step = 0; step <= offset; step += 1) {
        const before = undoStack.length;
        await performUndo();
        if (undoStack.length === before) break;
      }
    });
    li.appendChild(button);
    list.appendChild(li);
  });
  menu.appendChild(list);
  menu.classList.remove("hidden");
  const margin = 8;
  const anchor = anchorEl.getBoundingClientRect();
  menu.style.left = "0px";
  const box = menu.getBoundingClientRect();
  const left = Math.min(anchor.left, window.innerWidth - margin - box.width);
  menu.style.left = `${Math.round(Math.max(margin, left))}px`;
}

// One plain-English line: which search engine is active and whether it works.
// The built-in engine runs without Ollama, so this shows in every state.
function renderSearchEngineHealth(status) {
  const el = $("search-engine-health");
  // The name comes from the server, never from a string in here: this line
  // said "Built-in (all-MiniLM)" for two model changes after the built-in
  // model stopped being all-MiniLM, and the only way to find out what was
  // really running was to watch it download in the log.
  const engine =
    status.embedding_backend === "ollama"
      ? `Ollama · ${status.embedding_model}`
      : `Built-in · ${status.active_embedding_model || "…"}`;
  let state = "not ready";
  let cls = "busy";
  if (status.embedding_ready) {
    //: No tick in front of the word. The line already carries `status ok`,
    //: which is the green, and a typed check beside it was the app saying the
    //: same thing twice in two different alphabets: one of the plainer signs
    //: of a UI assembled from whatever was to hand (INBOX 263).
    state = "ready";
    cls = "ok";
  } else if (status.embedding_warming) {
    state = "… warming up";
  } else if (status.embedding_backend !== "ollama" && status.builtin_embedding_installing) {
    state = "installing, search uses keywords until it is done";
  } else if (status.embedding_backend !== "ollama" && status.builtin_embedding_installed === false) {
    //: "not ready" read as "wait", when nothing was coming (INBOX 431 (3)).
    state = "not installed, search uses keywords (install it under Packages)";
    cls = "error";
  } else if (status.embedding_error) {
    state = "Unavailable: using keyword search (details below)";
    cls = "error";
  }
  //: **In words: is it working, and how well** (INBOX 431 (3), the owner:
  //: "half the time I can't tell if it is working or how well"). How many
  //: notes it can find by meaning, a re-index's progress, and how the last
  //: search actually found its notes.
  const reindex = status.reindex;
  const cover = status.embedding_coverage;
  const parts = [state];
  if (reindex && reindex.status === "running" && reindex.total) {
    parts.push(`indexing ${reindex.done} of ${nounCount(reindex.total, "note")}`);
  } else if (status.embedding_ready && cover && cover.total) {
    parts.push(
      cover.indexed >= cover.total
        ? `all ${nounCount(cover.total, "note")} searchable by meaning`
        : `${cover.indexed} of ${nounCount(cover.total, "note")} searchable by meaning`
    );
  }
  const last = status.last_search?.mode;
  if (last) {
    parts.push(
      last === "keyword" ? "last search used keywords only"
        : last === "semantic" ? "last search matched by meaning"
          : "last search matched by meaning and keywords"
    );
  }
  el.textContent = `Search engine: ${engine}: ${parts.join(", ")}`;
  el.className = `status ${cls}`;
}

function renderBackendPicker(status) {
  const select = $("llm-provider-select");
  const url = $("llm-base-url");
  if (!select || !url) return;
  if (backendFieldsDirty || document.activeElement === url) return;
  select.value = status.provider || "ollama";
  // Show the address actually in use, but as a placeholder when it is just the
  // default: so the field stays empty and "blank means the usual one" keeps
  // being true after a round trip.
  const defaults = status.provider_default_base_urls || {};
  const fallback = defaults[select.value] || "";
  if (status.base_url && status.base_url !== fallback) {
    url.value = status.base_url;
  } else {
    url.value = "";
  }
  url.placeholder = fallback || "Default address";

  // Drawn from the status poll, not only from the Connect response. A warning
  // that shows once and disappears on the next reload is a warning about a
  // condition that has not gone away, and this one says the notes are leaving
  // the machine, which is the promise the whole app is built on.
  const privacy = $("llm-privacy-warning");
  if (privacy) {
    privacy.textContent = status.privacy_note || "";
    privacy.classList.toggle("hidden", !status.privacy_note);
  }
  const lock = $("local-only-ai");
  if (lock && document.activeElement !== lock) {
    lock.checked = status.local_only_ai !== false;
  }
}
