// semantic-notice.js: the one-time question before search by meaning is
// downloaded. Lazy (app.js `LAZY_MODULES.semanticNotice`), reached from the
// model status poll (status.js) only when /models/status says `semantic_offer`
// (a save wanted the model, nothing is on this computer and the question is
// still open), so the boot scripts carry a few lines of it and nothing else.
//
// The owner, 2026-10-27: nothing downloads without a yes. The model came from
// huggingface.co on the first saved note, unasked. Now the app asks once, in
// DESIGN.md's toast recipe (a toast with its actions and a close, kept up
// until it is answered because the message stays true until then). Download
// says yes and starts it as a Background task; No thanks, or closing the
// notice, says no. Either answer is kept (`semantic_choice_made`, set by the
// server when `semantic_auto_install` is written) and the question is not
// asked again; Settings, Search and index holds the switch either way, and
// search uses keywords meanwhile, with nothing shown as an error.

//: What the question says. `moved` is the server's `semantic_engine_moved`
//: (set when the old PyTorch copy of the model is on this computer): the
//: engine changed, so say what the one download replaces and whether the
//: notes are read again.
function semanticQuestionText(moved) {
  if (!moved) {
    return "Search by meaning needs a one-time download of about 130 MB from huggingface.co and pypi.org. Keyword search works meanwhile.";
  }
  const notes =
    moved.vectors === "kept"
      ? "Your notes keep their search data and nothing is embedded again."
      : "Your notes are read again in the background once it is here.";
  return `The search engine moved. A one-time download of ${moved.download} from huggingface.co and pypi.org replaces the old one. ${notes} Keyword search works meanwhile.`;
}

//: The open notice and whether this page has shown one. A host object, not
//: two top-level lets (tests/test_global_scope_ratchet.py).
const SEMANTIC_NOTICE = { note: null, shown: false };

async function semanticSetAutoInstall(on) {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ semantic_auto_install: on }),
  });
  const box = $("pref-semantic-auto-install");
  if (box) box.checked = on;
}

async function semanticAnswer(on) {
  try {
    await semanticSetAutoInstall(on);
  } catch (error) {
    toast(error.message, true);
    return;
  }
  if (on) {
    toast("Downloading search by meaning in the background.");
    refreshBackgroundTasks();
    return;
  }
  toastAction(
    "Search uses keywords. Turn on Download search by meaning in Settings, Search and index whenever you like.",
    "Undo",
    () => semanticAnswer(true),
    { go: { settings: "searchindex", focus: "pref-semantic-auto-install" } }
  );
}

//: Called on every status poll with the server's `semantic_offer` (and its
//: `semantic_engine_moved`), and with
//: false when the notice is open and the question has been answered
//: elsewhere (Settings), which closes it.
function semanticOffer(offered, moved) {
  const open = SEMANTIC_NOTICE.note;
  if (!offered) {
    if (open && open.isConnected) dismissToast(open);
    SEMANTIC_NOTICE.note = null;
    return;
  }
  if (SEMANTIC_NOTICE.shown) return;
  SEMANTIC_NOTICE.shown = true;
  const note = document.createElement("div");
  note.className = "toast semantic-install-toast";
  const text = document.createElement("span");
  text.className = "toast-msg";
  text.textContent = semanticQuestionText(moved);
  const answer = (on) => {
    dismissToast(note);
    SEMANTIC_NOTICE.note = null;
    semanticAnswer(on);
  };
  const yes = document.createElement("button");
  yes.type = "button";
  yes.className = "small toast-action";
  yes.textContent = "Download";
  yes.addEventListener("click", () => answer(true));
  const no = document.createElement("button");
  no.type = "button";
  no.className = "small toast-action";
  no.textContent = "No thanks";
  no.addEventListener("click", () => answer(false));
  const close = toastCloseButton(note, null);
  //: Closing is a no, the answer that touches nothing (as the update question).
  close.addEventListener("click", () => semanticSetAutoInstall(false).catch((error) => toast(error.message || "Couldn't save that choice. Settings, Search and index has the switch.", true)));
  note.append(text, toastActions(yes, no), close);
  const host = toastHost();
  toastStack(host, () => host.appendChild(note));
  SEMANTIC_NOTICE.note = note;
}

//: The same question on the welcome card (onboarding.js), where the first
//: diagnostics are read: the package is missing, so say what happens and let
//: the person decide before anything is downloaded. Only while the question
//: is open; an answered one is Settings' to change.
async function semanticOnboardingOffer(box) {
  const prefs = await apiJson("/preferences", { silent: true }).catch(() => null);
  if (!prefs || !box.isConnected || $("onboarding-overlay").classList.contains("hidden")) return;
  if (prefs.semantic_choice_made || prefs.semantic_auto_install) return;
  const button = smallButton(
    "Download search by meaning",
    prefs.semantic_engine_moved
      ? semanticQuestionText(prefs.semantic_engine_moved)
      : "A one-time download of about 130 MB from huggingface.co and pypi.org. Until then search uses keywords.",
    async () => {
      button.disabled = true;
      try {
        await semanticSetAutoInstall(true);
        button.textContent = "Downloading in the background";
      } catch (error) {
        button.disabled = false;
        toast(error.message, true);
      }
    }
  );
  box.classList.remove("hidden");
  box.appendChild(button);
}
