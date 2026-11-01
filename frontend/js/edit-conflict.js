// Lazily loaded (LAZY_MODULES.editConflict in app.js): the edit-conflict
// dialog runs only when a save comes back 409, so it stays off the boot
// scripts' gzip budget (tests/test_static_compression.py). The comment
// explaining the dialog is above isEditConflict in menus.js.

(() => {
  function editConflictPrompt({ noun = "note", mine = "", theirs = "" } = {}) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay confirm-overlay";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.setAttribute("aria-labelledby", "edit-conflict-title");
      const card = document.createElement("div");
      card.className = "card modal-card confirm-card edit-conflict-card";
      const text = document.createElement("p");
      text.className = "confirm-text";
      const title = document.createElement("strong");
      title.className = "confirm-title";
      title.id = "edit-conflict-title";
      title.textContent = `This ${noun} changed in another window`;
      const body = document.createElement("span");
      body.textContent = "It was saved somewhere else after you started editing here. Keep your version, take the other one, or compare them first.";
      text.append(title, document.createElement("br"), body);
      const compare = document.createElement("div");
      compare.className = "edit-conflict-compare hidden";
      const row = document.createElement("div");
      row.className = "row confirm-actions";

      let settled = false;
      const returnFocus = document.activeElement;
      const close = (answer) => {
        if (settled) return;
        settled = true;
        document.removeEventListener("keydown", onKey, true);
        overlay.remove();
        returnFocus?.focus?.();
        resolve(answer);
      };
      const onKey = (event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          close(null);
        }
      };
      let compareBtn = null;
      //: A second press while the diff builder is still loading drew the
      //: comparison twice, one under the other.
      let drawing = false;
      const drawCompare = async () => {
        if (drawing) return;
        if (!compare.classList.contains("hidden")) {
          compare.classList.add("hidden");
          setLabel(compareBtn, "Compare");
          return;
        }
        compare.replaceChildren();
        drawing = true;
        try {
          await ensureModule("library");
          //: The diff is drawn by documents-history.js, which the bundle does not carry.
          await lazyScript("/js/documents-history.js");
        } finally {
          drawing = false;
        }
        if (settled) return;
        const legend = document.createElement("p");
        legend.className = "muted edit-conflict-legend";
        legend.textContent = "Removed lines are the other window's, added lines are yours.";
        const host = document.createElement("div");
        docRenderDiff(host, docDiffLines(theirs, mine), { emptyText: "The two versions have the same text." });
        compare.append(legend, host);
        compare.classList.remove("hidden");
        setLabel(compareBtn, "Hide comparison");
      };
      const later = smallButton("Not now", "Keep editing without saving", () => close(null));
      compareBtn = smallButton("Compare", "Show what differs between the two versions", drawCompare);
      const theirsBtn = smallButton("Take theirs", "Load the other window's version into this editor", () => close("theirs"));
      const mineBtn = smallButton("Keep mine", "Save your version over the other one", () => close("mine"), false);
      row.append(later, compareBtn, theirsBtn, mineBtn);
      card.append(text, compare, row);
      overlay.appendChild(card);
      wireBackdropClose(overlay, () => close(null));
      document.addEventListener("keydown", onKey, true);
      document.body.appendChild(overlay);
      //: Focus on "Not now": a stray Enter must neither overwrite the other
      //: window's text nor throw away this one.
      later.focus();
    });
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { editConflictPrompt });
})();
