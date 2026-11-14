// feature-model-sheet.js: the per-feature model chooser sheet, moved out of ai-tools.js on 2026-10-12 for the boot gzip budget. Opened by a click or a menu row, return unread: `lazy-entries.js` stands in.

//: **The inline picker, one sheet for every surface.** Decision 4: "easily
//: altered" means not walking to Settings, and the way in is the surface's own
//: ⋯ rather than a new control in its chrome. `openSheet` is DESIGN.md's
//: recipe for a panel of choices and it is the one shape that works in all
//: three places, two of which hold a `kebabMenu` and one a `details.dock-menu`
//: that cannot nest a second menu inside itself.
(() => {
  function openFeatureModelSheet(key) {
    const row = featureModelRow(key);
    if (!row) {
      //: The words named the place; the button goes there (a toast action, not a link in prose).
      toastAction("Models aren't available yet.", "Open Settings, Models", () => openSettingsModal("models"));
      return;
    }
    openSheet({
      label: `Model for ${row.label}`,
      sub: featureModelState(row),
      name: `feature-model-${key}`,
      build: (card, close) => {

        const list = document.createElement("div");
        list.className = "sheet-list";
        list.appendChild(
          sheetRow(
            row.overridden ? "ph ph-arrow-counter-clockwise" : "ph ph-check",
            // The choice, not the state: the line under the title already says
            // which model is in use, so this row names what pressing it does.
            `Default (${row.inherits})`,
            () => {
              close();
              if (row.overridden) applyFeatureModel(key, "");
            }
          )
        );
        //: The two "Same as ..." rows (INBOX 430): a feature that wants to
        //: follow a role other than its own, on purpose, rather than being
        //: pinned to one model that goes stale the moment that role changes.
        //: The Chat tab's own sheet leaves "Same as chat model" out: for the
        //: chat feature it is the Default row said twice (wc2-1110).
        if (key !== "chat") {
          list.appendChild(
            sheetRow(
              row.override_kind === "chat" ? "ph ph-check" : "ph ph-arrows-clockwise",
              "Same as chat model",
              () => {
                close();
                if (row.override_kind !== "chat") applyFeatureModel(key, featureModelFollow.chat);
              }
            )
          );
        }
        list.appendChild(
          sheetRow(
            row.override_kind === "utility" ? "ph ph-check" : "ph ph-arrows-clockwise",
            "Same as utility model",
            () => {
              close();
              if (row.override_kind !== "utility") applyFeatureModel(key, featureModelFollow.utility);
            }
          )
        );
        for (const name of featureModelNames) {
          const chosen = row.override_kind === "model" && row.override_value === name;
          list.appendChild(
            sheetRow(chosen ? "ph ph-check" : "ph ph-cube", name, () => {
              close();
              if (!chosen) applyFeatureModel(key, name);
            })
          );
        }
        card.appendChild(list);
        //: A backend that is not answering has no model list to offer, and the
        //: sheet says so rather than showing one row and letting the reader
        //: wonder where their models went.
        if (!featureModelNames.length) {
          const empty = document.createElement("p");
          empty.className = "muted";
          empty.textContent =
            "No models are installed, or the model server isn't answering.";
          card.appendChild(empty);
        }
      },
    });
  }

  //: The dock pills (the owner, 2026-11-12: "Yes, a dock pill"): the feature's resolved model (its own pick,
  //: else its role's) as the `#chat-active-model` recipe, hidden while no model server answers, as that pill is.
  //: Moved here from ai-tools.js (L624): ai-tools.js fetches this file when the notes or documents surface is
  //: built, and calls `syncFeatureModelSelects.pills?.()` on every poll. A property, not a global.
  function syncFeatureModelPills() {
    for (const pill of document.querySelectorAll("[data-feature-pill]")) {
      const row = featureModelRow(pill.dataset.featurePill);
      const off = !row || modelStatus?.ollama_running === false;
      pill.hidden = off;
      if (off) continue;
      pill.textContent = shortModelName(row.model);
      pill.title = `${row.label} runs on ${row.model}${row.overridden ? "" : ", inherited"}: click to change it`;
    }
  }
  syncFeatureModelSelects.pills = syncFeatureModelPills;
  syncFeatureModelPills();
  document.addEventListener("click", (event) => {
    const pill = event.target.closest?.("[data-feature-pill]");
    if (pill) openFeatureModelSheet(pill.dataset.featurePill);
  });

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { openFeatureModelSheet });
})();
