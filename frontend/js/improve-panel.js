// improve-panel.js: the Improve sheet (rewrite the draft with the model), moved out of ai-tools.js on 2026-10-12 for the boot gzip budget. Opened by a click; `LAZY_ENTRY_POINTS.improvePanel` (app.js) stands in for its entry points until this loads. `improveMode` and `improveCustomInstruction` stay in ai-tools.js.

function openImprove(targetTextarea) {
  const text = targetTextarea.value.trim();
  if (!text) {
    toast("Write something first, then improve it.", "info");
    return;
  }
  improveTarget = targetTextarea;
  improveMode = "proofread";
  improveCustomInstruction = "";
  $("improve-custom-input").value = "";
  $("improve-custom-row").classList.add("hidden");
  for (const b of document.querySelectorAll(".improve-mode"))
    b.classList.toggle("active", b.dataset.mode === "proofread");
  $("improve-original").textContent = text;
  overlayReturnFocus = document.activeElement;
  $("improve-overlay").classList.remove("hidden");
  $("improve-close").focus();
  improveReady();
}

//: **Asked for, not automatic** (the owner at release: "the improve writing
//: panel should be a begin AI response thing"): opening the panel, or picking
//: a mode, only gets it ready; Atlas starts on Start. The button reads Try
//: again once there has been an answer to try again.
function improveReady() {
  const custom = improveMode === "custom";
  $("improve-status").textContent = custom
    ? "Say what you want changed, then press Go."
    : "Pick how Atlas should help, then press Start.";
  $("improve-status").classList.remove("error");
  $("improve-result").textContent = "";
  $("improve-apply").disabled = true;
  setLabel($("improve-retry"), "ph:sparkle Start");
}

function closeImprove() {
  $("improve-overlay").classList.add("hidden");
  overlayReturnFocus?.focus?.();
  overlayReturnFocus = null;
}

async function runImprove() {
  const status = $("improve-status");
  const result = $("improve-result");
  if (improveMode === "custom" && !improveCustomInstruction.trim()) {
    // Nothing to send yet, the box just opened on "Custom" and the person
    // hasn't typed anything. Prompting here instead of calling the API with
    // an empty instruction (which the backend would reject anyway) so the
    // very first thing that happens after picking Custom isn't an error.
    status.textContent = "Say what you want changed, then press Go.";
    status.classList.remove("error");
    result.textContent = "";
    $("improve-apply").disabled = true;
    return;
  }
  result.textContent = "";
  setLabel($("improve-retry"), "ph:arrow-clockwise Try again");
  setLabel(status, "ph:spin Atlas is editing…");
  status.classList.remove("error");
  $("improve-apply").disabled = true;
  try {
    const body = await apiJson("/entries/improve", {
      method: "POST",
      body: JSON.stringify({
        text: $("improve-original").textContent,
        mode: improveMode,
        custom_instruction: improveMode === "custom" ? improveCustomInstruction.trim() : undefined,
      }),
    });
    result.textContent = body.improved;
    //: With no model the app proofreads itself (O7, INBOX 904 B33) and says
    //: so: who did it and what it changed, never "Atlas's suggestion".
    status.textContent = body.by === "composer" ? body.said || "" : "";
    result.dataset.by = body.by === "composer" ? "composer" : "";
    $("improve-apply").disabled = body.improved === $("improve-original").textContent;
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  }
}

function applyImprove() {
  if (improveTarget) {
    improveTarget.value = $("improve-result").textContent;
    //: The save that follows is the person's and Atlas's (INBOX 446).
    improveTarget.dataset.aiTouched = "1";
    improveTarget.dispatchEvent(new Event("input")); // refresh char count
  }
  closeImprove();
  toast($("improve-result").dataset.by === "composer" ? "Applied the proofreading." : "Applied Atlas's suggestion.");
}
