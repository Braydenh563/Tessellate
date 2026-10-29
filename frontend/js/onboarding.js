// onboarding.js: the first-run welcome card (five slides' worth of text, the
// setup check with its two one-click offers, and the card's own buttons).
// Moved out of settings-wiring.js on 2026-10-05 (the boot-script gzip budget,
// ratchet in tests/test_static_compression.py): the card opens once per
// notebook, or when someone presses "Replay the welcome", so nothing here is
// needed to draw the first screen. Loaded on first use by
// `LAZY_MODULES.onboarding` (app.js), whose stand-in for `openOnboarding`
// fetches this file and then calls the real one. `maybeShowOnboarding` stays
// in settings-wiring.js, because it is what decides whether to open the card
// at all and it is a dozen lines. The three buttons are wired here, at the
// bottom: they are only on screen while the card is, and the card only opens
// through `openOnboarding`, so the wiring has always run by the time they can
// be pressed.

// --- first-run onboarding tour (learnability) -------------------------------

const ONBOARDING_SLIDES = [
  {
    icon: "ph:sparkle",
    title: "Welcome to Tessellate",
    //: **"Out of the box", not "ever".** Measured 2026-09-21: two features
    //: make outbound requests, web search and the update check, and both are
    //: off by default (`core/config.py`), so the claim is exactly true until
    //: the person turns one on and false the moment they do. Saying so is
    //: stronger than the absolute, not weaker: this sentence sits in the same
    //: Settings area as both switches, and a promise the app itself offers to
    //: break is the kind a privacy-minded reader checks and stops trusting.
    text: "A 100% offline notebook where a local AI files your thoughts and answers questions about them. Out of the box nothing leaves this computer. Two features can, web search and the update check, and both stay off until you turn them on.",
  },
  // §27: "before the person's first capture fails silently into
  // Uncategorised and they assume the AI is broken rather than absent", so
  // this sits before the capture slide, not after. `dynamic` is filled in by
  // `loadOnboardingDiagnostics` once the overlay is actually showing it,
  // reusing /models/status and /storage rather than a new endpoint, both
  // already exist and are already polled elsewhere in the app.
  {
    icon: "ph:stethoscope",
    title: "Your setup",
    dynamic: true,
  },
  // **The seven slides that used to follow this one are the guided tour now**
  // (frontend/js/tour.js). They described a tab in prose, "the Graph tab draws
  // how your notes connect", "press Ctrl+K anywhere", from the middle of a
  // screen that was covering the tab bar those words were about, which is the
  // gap the owner named: "there is no guided tour and introduction, with
  // positioned popup cards". Nothing was dropped: every one of them is a step
  // in TOUR_SECTIONS anchored to the control it used to describe, which is
  // both shorter to read and the only version that can point at anything.
  //
  // What stays here is what an anchored card cannot do. The welcome says what
  // Tessellate is before there is any interface to point at, and the setup
  // slide is a live check of Ollama and the notebook's folder with its two
  // one-click offers (pull a model, seed example notes) on it: a card the size
  // of a sentence, hung off a control, is the wrong place for either. So the
  // two surfaces are kept apart on purpose, the welcome ends by handing over
  // to the tour, and Settings, help and guide offers them separately.
];

const onboardingRun = { index: 0, diagnosticsToken: 0 };
// A stale diagnostics fetch (the user clicked Next or Skip before it
// resolved) must never overwrite whichever slide is showing by the time it
// lands: this is what tells a resolved probe whether it still applies.

// §27's first-run diagnostics: Ollama reachability and where the notebook
// actually lives, both already computed for other UI (the AI-status pill,
// Settings → Data) and just not surfaced before a first capture could fail
// silently into Uncategorised.
async function loadOnboardingDiagnostics(forSlide) {
  const token = ++onboardingRun.diagnosticsToken;
  const [models, storage, notebook] = await Promise.all([
    apiJson("/models/status").catch(() => null),
    apiJson("/storage").catch(() => null),
    apiJson("/entries/count").catch(() => null),
  ]);
  if (token !== onboardingRun.diagnosticsToken) return; // superseded by a later slide
  if (onboardingRun.index !== forSlide) return; // the user moved on already
  if ($("onboarding-overlay").classList.contains("hidden")) return; // or closed it

  const lines = [];
  lines.push(
    models && models.ollama_running
      ? "Ollama is running, so Atlas will file your notes and answer questions."
      : "No model is running yet, and Tessellate works without one: notes are " +
          "searched by keyword, and filing catches up once a model is on."
  );
  //: A first install needs the internet once (BACKLOG, Brief 40): said where
  //: the download is offered, with the size of the set that would come down.
  if (models?.builtin_embedding_installed === false && models.builtin_embedding_download_mb) {
    lines.push(
      "The first setup downloads the search model and the packages you chose " +
        `(about ${models.builtin_embedding_download_mb} MB); after that Tessellate works offline.`
    );
  }
  if (storage) {
    //: Where it lives, and its size once there is one (INBOX 472).
    const mb = (storage.database_bytes || 0) / (1024 * 1024);
    lines.push(
      mb >= 0.1
        ? `Your notebook lives at ${storage.data_dir} (${mb.toFixed(1)} MB).`
        : `Your notebook lives at ${storage.data_dir}.`
    );
    // ROADMAP.md's onboarding item named this the one still-open piece: a
    // data-dir writability check. The database opening at all already
    // implies it was writable at boot, but a synced folder, a permissions
    // change, or a disk remounted read-only can flip that afterwards with
    // nothing in the interface ever saying so, a save just starts failing,
    // on the one screen this app has that already knows where the notebook
    // lives and is looking right at it.
    if (storage.data_dir_writable === false) {
      lines.push(
        "That folder isn't writable right now, so new notes and edits won't " +
          "save. Check its permissions, or move the notebook somewhere " +
          "Tessellate can write to (Settings → Account & security)."
      );
    }
  } else {
    lines.push("Couldn't check where your notebook lives just now.");
  }
  $("onboarding-text").textContent = lines.join(" ");
  renderOnboardingActions(models, notebook);
}

// The two concrete gaps ROADMAP.md named for onboarding: offering to pull a
// model, and seeding example notes so the Graph/Timeline/Dashboard aren't
// empty on a first look. Both are one-click offers on the setup slide,
// never automatic: a fresh install with no notes and no model is exactly
// the state a real, deliberate first run looks like too, so this only ever
// acts on an explicit click.
function renderOnboardingActions(models, notebook) {
  const box = $("onboarding-actions");
  box.replaceChildren();
  const offers = [];

  if (models && models.ollama_running && !models.chat_model_installed) {
    offers.push(
      smallButton(
        "Download a starter model",
        "Pull llama3.2 (~2.2 GB) with Ollama, in the background",
        async (event) => {
          const offer = event.currentTarget;
          setBusy(offer, true, "Downloading in the background…");
          try {
            await api("/models/pull", {
              method: "POST",
              body: JSON.stringify({ name: "llama3.2" }),
            });
            refreshModelStatus();
          } catch (error) {
            setBusy(offer, false);
            toast(error.message || "Couldn't start the download.", true);
          }
        },
        false
      )
    );
  }

  //: AI off: offer the way to turn it on (INBOX 472).
  if (models && !models.ollama_running) {
    offers.push(
      smallButton(
        "ph:plugs Connect a model",
        "Close the welcome and open Settings at Models, where a model is connected",
        //: Settings first, the welcome closes once it is up: Settings loads
        //: lazily, and closing first let the first-run queue see a clear
        //: screen and draw the recovery offer over the page this button had
        //: just opened (scan 2026-10-11).
        () => {
          Promise.resolve(openSettingsModal("models")).catch(() => {}).then(() => closeOnboarding());
        }
      )
    );
  }

  if (notebook && notebook.count === 0) {
    offers.push(
      smallButton(
        "Add example notes",
        "Seed a few linked notes so the Graph, Timeline and Dashboard have something to show",
        async (event) => {
          event.target.disabled = true;
          try {
            const result = await apiJson("/entries/seed-examples", { method: "POST" });
            const count = result && result.created ? result.created : 0;
            event.target.textContent = count ? `Added ${count} example notes` : "Added";
            loadEntries();
            //: **Added, and the welcome stays put** (INBOX 745 (d), the
            //: owner: "should it have gone straight to the graph tour?? i
            //: clicked add some example notes"). Where to see them, and the
            //: tour, are two offers in one toast, each said in words; nothing
            //: opens until one is pressed. The welcome's own primary still
            //: names where it goes ("Start the tour").
            toastAction(
              count ? `Added ${count} example notes, tagged "welcome".` : "Added the example notes.",
              "See them on the graph",
              () => {
                closeOnboarding(false);
                switchTab("graph");
              },
              {
                record: false,
                also: {
                  label: "Take the tour",
                  run: () => {
                    closeOnboarding(true);
                    openTour("basics");
                  },
                },
              }
            );
          } catch (error) {
            event.target.disabled = false;
            toast(error.message || "Couldn't add the example notes.", true);
          }
        },
        false
      )
    );
  }

  //: **"I have 4,000 notes in Obsidian, now what"** (BACKLOG 112.4 item 4):
  //: an empty notebook is also offered the way in for notes kept elsewhere,
  //: Settings, Import & export, whose Import files takes Markdown folders as
  //: they are. The welcome closes first so the two never overlap.
  if (notebook && notebook.count === 0) {
    offers.push(
      smallButton("ph:file-arrow-up Bring in your notes", "Import Markdown files or a folder, such as an Obsidian vault", () => {
        closeOnboarding(false);
        openSettingsModal("data", "import-md");
      })
    );
  }

  box.classList.toggle("hidden", offers.length === 0);
  for (const button of offers) box.appendChild(button);
  if (models?.builtin_embedding_installed === false)
    semanticOnboardingOffer(box);
}

function renderOnboardingSlide() {
  const slide = ONBOARDING_SLIDES[onboardingRun.index];
  setLabel($("onboarding-icon"), slide.icon);
  //: **Atlas says hello on the first card** (the owner: "atlas should also
  //: be in the welcome tour as well to greet new users"). Its own face,
  //: pleased and always moving, with one line in its own voice; the later
  //: cards keep the app's logo, so a new person meets both.
  const atlas = $("onboarding-atlas");
  const greet = onboardingRun.index === 0 && typeof atlasMark === "function";
  atlas.classList.toggle("hidden", !greet);
  $("onboarding-emblem").classList.toggle("hidden", greet);
  //: One mark per card (INBOX 472).
  $("onboarding-icon").classList.add("hidden");
  if (greet) {
    const face = document.createElement("span");
    face.className = "nm-live";
    //: The swirl and orbit paint up to 4px past the svg's own box (measured
    //: at 390); the holder's padding keeps them inside it, off the bubble.
    face.style.padding = "var(--space-1)";
    face.appendChild(atlasMark(104, "happy"));
    const say = document.createElement("p");
    say.className = "onboarding-atlas-say";
    say.textContent = `Hi, I'm ${aiNameNow()}. I'll file what you write and find it again when you ask.`;
    atlas.replaceChildren(face, say);
  }
  $("onboarding-title").textContent = slide.title;
  if (slide.dynamic) {
    setLabel($("onboarding-text"), "ph:spin Checking Ollama and where your notebook lives…");
    loadOnboardingDiagnostics(onboardingRun.index);
  } else {
    $("onboarding-text").textContent = slide.text;
  }
  const dots = $("onboarding-dots");
  dots.replaceChildren();
  ONBOARDING_SLIDES.forEach((_, i) => {
    const dot = document.createElement("span");
    dot.className = "onboarding-dot" + (i === onboardingRun.index ? " active" : "");
    dots.appendChild(dot);
  });
  $("onboarding-back").classList.toggle("hidden", onboardingRun.index === 0);
  const last = onboardingRun.index === ONBOARDING_SLIDES.length - 1;
  // "Start the tour", not "Get started": the last press of the welcome now
  // opens the tour's first section rather than dropping somebody on the
  // Dashboard with nothing said about where anything is. The word has to say
  // so, or the tour arrives as a surprise on top of a card they just closed.
  const tourOn = typeof TOUR_ENABLED === "undefined" || TOUR_ENABLED;
  $("onboarding-next").textContent = last ? (tourOn ? "Start the tour" : "Get started") : "Next";
  //: **And the other answer to that offer, in words** (the owner, 2026-09-21:
  //: "add a skip guided tour button to the welcome intro panels"). The left
  //: button has always closed the welcome and counted as declining the tour,
  //: which `closeOnboarding` records, but on the last slide it still said
  //: "Skip" beside a primary that says "Start the tour", so the one thing it
  //: was answering was the one thing it did not name. It names it there.
  const skip = $("onboarding-skip");
  skip.textContent = last && tourOn ? "Skip the tour" : "Skip";
  skip.title = last
    ? "Go straight to the app. You can start the tour any time from Settings, Help."
    : "Close the welcome and go straight to the app";
}

//: **First run: one thing at a time** (the owner, 2026-10-10: "popups and
//: notifications clash with each other, the tour gets cancelled, to much goes
//: on"). Measured on a fresh data dir before this: the recovery-key offer drew
//: over the welcome card (478x172 px of overlap), and the update question
//: opened on "onboarding-closed" at the same moment as the tour, so the tour
//: judged its steps against the question's overlay, kept one ("1 of 1, Find
//: ... not on screen") and drew its card on top of the question. Each first-run
//: surface now takes a turn, in the order measured on a fresh data dir: the
//: welcome, the tour if the welcome started it, the recovery-key offer, then
//: the update question. `show` returns a promise that settles when its surface is done;
//: the next turn also waits until nothing modal is on screen, so a surface
//: that forgets to say when it closed cannot open the next one on top of it.
//: **A fixed order, not first come** (the owner, 2026-10-11, from the Windows
//: app: "popup panels appearing at the start on a new install are messy and
//: clash/overlap a lot"). The chain this replaced ran turns in the order they
//: were asked for, and two first-run surfaces never asked at all: the desktop
//: app's "Keep a console window open" question went straight to the screen
//: on the same `looksReady` as the welcome, so in the Windows app it opened
//: over the welcome card (the one surface a headless sweep cannot see unless
//: it fakes `/health`'s `desktop`). Now every surface names its slot in
//: `FIRST_RUN_ORDER`, the queue shows the lowest slot waiting, and on a first
//: run (no `onboardingDone`) nothing opens until the welcome has had its turn.
const FIRST_RUN_ORDER = ["welcome", "recovery", "console", "updates"];
//: How long the queue holds the others for a welcome that never arrives (its
//: module failed to load): a stuck queue would hide the recovery offer for good.
const FIRST_RUN_WELCOME_WAIT_MS = 15000;
const firstRun = { waiting: [], running: false, clearSince: 0 };

function firstRunSurfaceOpen() {
  const shown = (id) => {
    const el = $(id);
    return Boolean(el && !el.classList.contains("hidden"));
  };
  //: Settings too: the welcome's "Connect a model" opens it, and the recovery
  //: offer used to draw over it (scan 2026-10-11), on top of the very page the
  //: person had just been sent to. It takes its turn when Settings closes.
  //: The lock screen too: a surface queued at setup waits for the notebook.
  return shown("lock-overlay") || shown("onboarding-overlay") || shown("tour-card") || shown("settings-modal") ||
    Boolean(document.querySelector("dialog[open], .confirm-overlay"));
}

function whenFirstRunClear() {
  return new Promise((resolve) => {
    const tick = () => (firstRunSurfaceOpen() ? setTimeout(tick, 250) : resolve());
    tick();
  });
}

function firstRunToastsGone(capMs) {
  const until = Date.now() + capMs;
  return new Promise((resolve) => {
    const tick = () => {
      const up = [...document.querySelectorAll(".toast")].some((t) => t.getClientRects().length);
      return up && Date.now() < until ? setTimeout(tick, 250) : resolve();
    };
    tick();
  });
}

//: `show` opens one surface and returns a promise that settles when it is
//: done; `slot` is its name in `FIRST_RUN_ORDER`. Resolves to what `show`
//: resolved to (the update and console questions read their answer from it).
function firstRunTurn(show, slot) {
  return new Promise((resolve) => {
    firstRun.waiting.push({ show, rank: FIRST_RUN_ORDER.indexOf(slot), resolve, slot });
    firstRunPump();
  });
}

function firstRunWelcomeDue() {
  if (prefs.get("onboardingDone", null)) return false;
  if (firstRun.waiting.some((item) => item.slot === "welcome")) return false;
  //: Counted from the first clear screen, not from the module's load: the
  //: lock's opening curtain can outlast the wait on a slow machine.
  return Date.now() - firstRun.clearSince < FIRST_RUN_WELCOME_WAIT_MS;
}

async function firstRunPump() {
  if (firstRun.running) return;
  firstRun.running = true;
  try {
    while (firstRun.waiting.length) {
      await whenFirstRunClear();
      firstRun.clearSince ||= Date.now();
      //: A beat for whatever the same boot step is about to queue, so the
      //: slot order, not the arrival order, decides who goes next.
      await new Promise((r) => setTimeout(r, 300));
      //: And the last surface's own toast read first ("That is the tour",
      //: "You can make a recovery key later"): at 390 they drew over the
      //: next question's card (337x47 px). Six seconds at most.
      await firstRunToastsGone(6000);
      if (firstRunWelcomeDue()) continue;
      firstRun.waiting.sort((a, b) => a.rank - b.rank);
      const item = firstRun.waiting.shift();
      let answer;
      try {
        answer = await item.show();
      } catch {
        answer = undefined;
      }
      item.resolve(answer);
    }
  } finally {
    firstRun.running = false;
  }
}

//: The welcome's turn ends when the welcome closes and, when its last button
//: started the tour, when the tour ends too (`tour-closed`, tour.js). Without
//: the second wait the gap while tour.js loads looked like a clear screen.
function showOnboardingTurn() {
  return new Promise((resolve) => {
    document.addEventListener("onboarding-closed", (event) => {
      if (!event.detail?.tour) return resolve();
      document.addEventListener("tour-closed", () => resolve(), { once: true });
      //: A tour that never opens (tour.js failed to load) must not hold the
      //: queue for ever.
      setTimeout(() => {
        if (!firstRunSurfaceOpen()) resolve();
      }, 8000);
    }, { once: true });
    showOnboarding();
  });
}


//: A first run's welcome waits its turn; "Replay the welcome" opens at once.
function openOnboarding() {
  if (!prefs.get("onboardingDone", null)) return firstRunTurn(showOnboardingTurn, "welcome");
  showOnboarding();
}

function showOnboarding() {
  onboardingRun.index = 0;
  overlayReturnFocus = document.activeElement;
  renderOnboardingSlide();
  $("onboarding-overlay").classList.remove("hidden");
  $("onboarding-next").focus();
}

function closeOnboarding(withTour = false) {
  $("onboarding-overlay").classList.add("hidden");
  prefs.set("onboardingDone", "1");
  // Skipping the welcome is also an answer about the tour: whoever closed this
  // card has been offered the introduction and said no, so nothing may open
  // the tour at them by itself afterwards. `tourClose` writes the same key
  // when the tour itself ends, and Settings, help and guide is the way back to
  // either of them.
  prefs.set("tourDone", "1");
  overlayReturnFocus?.focus?.();
  //: Whatever waited for the welcome (the first start's update question).
  //: `tour` says the tour is opening next, so the first-run queue
  //: (`firstRunTurn`, above) waits for it as well.
  document.dispatchEvent(new CustomEvent("onboarding-closed", { detail: { tour: withTour === true } }));
  overlayReturnFocus = null;
}

function onboardingNext() {
  if (onboardingRun.index >= ONBOARDING_SLIDES.length - 1) {
    const tourOn = typeof TOUR_ENABLED === "undefined" || TOUR_ENABLED;
    closeOnboarding(tourOn);
    // The hand-off: the welcome says what this is, the tour says where things
    // are, and the last press of the one starts the other. Guarded because
    // tour.js is a separate file loaded after this one, and a page served
    // without it must still close the welcome cleanly.
    //: Only if the tour is switched on: `TOUR_ENABLED` in tour.js is the one
    //: flag, and the welcome's primary is relabelled to match.
    //: Before tour.js has loaded (a lazy bundle) the flag is not defined
    //: yet and `openTour` is the stand-in that fetches it.
    if (tourOn) openTour("basics");
    return;
  }
  onboardingRun.index += 1;
  renderOnboardingSlide();
}

function onboardingBack() {
  if (onboardingRun.index === 0) return;
  onboardingRun.index -= 1;
  renderOnboardingSlide();
}

$("onboarding-next").addEventListener("click", onboardingNext);
$("onboarding-back").addEventListener("click", onboardingBack);
$("onboarding-skip").addEventListener("click", () => closeOnboarding(false));

// Moved from app.js (its gzip cap); `startApp` loads this bundle for it
// only while the question is unanswered.
// First-run "Dev view or User view?" prompt for the desktop app, gated on its
// own preference (console_view_intro_seen). Two fixed bugs: it fired on a
// stale-token startApp() before sign-in (prefsCache null), so it now needs
// prefsCache; and it POSTed /system/console-mode, which restarts the process
// and signed people out mid-login, so it is one PUT of both preferences,
// taking effect next launch.
async function maybeShowConsoleViewIntro() {
  if (!(await desktopShell())) return;
  if (!prefsCache || prefsCache.console_view_intro_seen) return;
  //: A first-run surface, so it takes its turn (`firstRunTurn`, above): it
  //: used to open over the welcome card in the Windows app.
  const wantsDevView = await firstRunTurn(() => confirmDialog(
    "Keep a console window open when Tessellate starts?\n\n" +
      "Dev view shows a terminal window alongside the app, useful for " +
      "logs and troubleshooting. User view runs quietly in the background " +
      "with no console window at all, just this app window and a system " +
      "tray icon. Either way, you can switch any time from Settings or " +
      "the tray icon's own menu.\n\nTakes effect next launch.",
    { confirmLabel: "Dev view", cancelLabel: "User view", danger: false }
  ), "console");
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({
        show_console_on_startup: wantsDevView,
        console_view_intro_seen: true,
      }),
    });
    toast(
      `${wantsDevView ? "Dev" : "User"} view: starting from next launch.`
    );
  } catch (error) {
    toast(error.message || "Couldn't save your console view choice.", true);
  }
}
