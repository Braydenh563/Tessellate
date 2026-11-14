// The guided tour, measured: every step of every section at 1440x900,
// 1184x760 and 390x844, each one judged on the things that made the owner
// call it "completely broken on all the slides except the first one"
// (2026-09-23): the control it names is laid out, inside the window and NOT
// under anything else; the cut-out sits on it; the card is on screen and clear
// of it; the tab and Notes sub-tab the step needs are the ones showing; the
// counter says the same total from the first card to the last.
//
// Since INBOX 398 the sections chain: the welcome and Start the tour each walk
// every section in order (the same cards both ways), every section is also
// played on its own and ended with Finish, the count is checked per section,
// the last card of each section must read "Next: <section>" beside Finish,
// Back across a section boundary is checked, a notebook with no mind map is
// simulated, and the notebook's boards and entries are counted before and
// after to prove the tour made nothing. Each walk prints "shown/planned" per
// section, naming every step it dropped.
//
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers BASE=http://127.0.0.1:8797 \
//     node scratchpad/ui-sweeps/tour.js            # all four sizes
//   SIZES=390x844 node scratchpad/ui-sweeps/tour.js  # one
//   SIZES=1600x890@1.25 ...                          # with a device scale
//   FULL=0 ...                                       # skip the second full walk
//
// Then the cases that broke it and that no clean walk sees: the tour started
// with an overlay open (the Atlas guide, the command palette, the features
// browser, the shortcut sheet), a resize across the phone breakpoint mid-step,
// typing in the lit control, Next pressed twice while a tab loads, and every
// door into the tour being live. Every line printed is a number or a
// comparison; the one visual claim ("the lit control is the bright thing") is
// settled with scratchpad/pngpixel.py on a capture.
//
// `lib.js` marks the welcome AND the tour as done before the app boots, so
// neither opens by itself mid-sweep; this sweep opens the tour itself.
const { boot } = require("./lib.js");
const { execFileSync } = require("child_process");
const path = require("path");

const ROOT = path.resolve(__dirname, "../..");
const SHOTS = (process.env.SCRATCH || "/tmp") + "/tour-shots";
require("fs").mkdirSync(SHOTS, { recursive: true });

//: Seconds since the sweep began, printed at each phase so a slow one is named, not guessed.
const T0 = Date.now();
const lap = (what) => console.log(`lap ${((Date.now() - T0) / 1000).toFixed(1)}s ${what}`);
const failures = [];
let stepsPassed = 0;
let stepsSeen = 0;
function check(ok, line) {
  if (!ok) failures.push(line);
  console.log(`${ok ? "ok  " : "FAIL"}  ${line}`);
  return ok;
}

//: Waits on the state a step needs, not on a guess at how long it takes (the sweep ran past 400 s
//: on fixed sleeps). `frames` is two animation frames: what a placement needs once the state is true.
const frames = (page) => page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
async function goTab(page, tab) {
  await page.evaluate((t) => switchTab(t), tab);
  await page.waitForFunction((t) => openTour.inspect.activeTab() === t, tab, { timeout: 8000 });
  await frames(page);
}
// The tour is closed and its three layers are hidden (a miss shows up in the check that follows).
async function closed(page) {
  await page
    .waitForFunction(
      () => !openTour.inspect.run && ["tour-card", "tour-spot", "tour-block"].every((id) => document.getElementById(id).classList.contains("hidden")),
      null,
      { timeout: 3000 }
    )
    .catch(() => {});
  await frames(page);
}
// Settings at its Help panel, built on first open (the replay rows, Start the tour, About's button).
async function openHelp(page) {
  await page.evaluate(() => openSettingsModal());
  await page.waitForFunction(() => typeof showSettingsSection === "function" && document.getElementById("settings-nav"), null, { timeout: 8000 });
  await page.evaluate(() => showSettingsSection("help"));
  await page.waitForFunction(
    () => document.getElementById("tour-start-btn") && document.querySelector('#settings-nav button.active[data-section="help"]'),
    null,
    { timeout: 8000 }
  );
  await frames(page);
}

// One step, from outside. Everything the step's pass or fail depends on.
const STEP_PROBE = () => {
  const card = document.getElementById("tour-card");
  const spot = document.getElementById("tour-spot");
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const c = card.getBoundingClientRect();
  const s = spot.getBoundingClientRect();
  const el = openTour.inspect.run.el;
  const t = el ? el.getBoundingClientRect() : { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 };
  const overlapW = Math.min(c.right, t.right) - Math.max(c.left, t.left);
  const overlapH = Math.min(c.bottom, t.bottom) - Math.max(c.top, t.top);
  const gaps = [t.left - c.right, c.left - t.right, t.top - c.bottom, c.top - t.bottom];
  // What is actually on top of the control, at five points, ignoring the
  // tour's own layers (they are drawn around the hole, never in it).
  let covered = 0;
  let counted = 0;
  const coveredBy = [];
  if (el) {
    for (const [fx, fy] of [[0.5, 0.5], [0.2, 0.3], [0.8, 0.3], [0.2, 0.7], [0.8, 0.7]]) {
      const x = t.left + t.width * fx;
      const y = t.top + t.height * fy;
      if (x < 0 || y < 0 || x >= vw || y >= vh) continue;
      counted += 1;
      const top = document
        .elementsFromPoint(x, y)
        .find((n) => !n.closest("#tour-block, #tour-spot, #tour-card, #toast-box"));
      if (!top || !(el.contains(top) || top.contains(el))) {
        covered += 1;
        coveredBy.push(top ? top.id || String(top.className).slice(0, 30) : "nothing");
      }
    }
  }
  const style = el ? getComputedStyle(el) : null;
  const step = openTour.inspect.run.step;
  const notesShown = step.notes
    ? !document.getElementById(step.notes)?.classList.contains("hidden")
    : true;
  return {
    target: step.target,
    shownTarget: el ? (el.id ? `#${el.id}` : el.className) : "none",
    alt: Boolean(openTour.inspect.run.alt),
    counter: document.getElementById("tour-count").textContent,
    section: document.getElementById("tour-section").textContent,
    title: document.getElementById("tour-title").textContent,
    text: document.getElementById("tour-text").textContent,
    side: card.dataset.side,
    stranded: Boolean(openTour.inspect.run.stranded),
    card: [Math.round(c.left), Math.round(c.top), Math.round(c.width), Math.round(c.height)],
    spot: [Math.round(s.left), Math.round(s.top), Math.round(s.width), Math.round(s.height)],
    anchor: [Math.round(t.left), Math.round(t.top), Math.round(t.width), Math.round(t.height)],
    vw,
    vh,
    exists: Boolean(el && el.isConnected),
    laidOut: Boolean(el) && t.width >= 1 && t.height >= 1 && style.visibility !== "hidden" && style.display !== "none",
    // Inside the window: the whole control when it fits, and at least the
    // tour's own 8px each way when it is bigger than the window.
    inWindow:
      Boolean(el) &&
      (t.width <= vw && t.height <= vh
        ? t.left >= -0.5 && t.top >= -0.5 && t.right <= vw + 0.5 && t.bottom <= vh + 0.5
        : Math.min(t.right, vw) - Math.max(t.left, 0) >= 8 && Math.min(t.bottom, vh) - Math.max(t.top, 0) >= 8),
    covered: counted === 0 || covered * 2 > counted,
    coveredBy,
    spotHidden: spot.classList.contains("hidden"),
    spotCovers:
      s.left <= Math.max(0, t.left) + 1 &&
      s.top <= Math.max(0, t.top) + 1 &&
      s.right >= Math.min(vw, t.right) - 1 &&
      s.bottom >= Math.min(vh, t.bottom) - 1,
    overlap: overlapW > 0 && overlapH > 0 ? Math.round(overlapW * overlapH) : 0,
    gap: Math.round(Math.max(...gaps)),
    cardInside: c.left >= -0.5 && c.top >= -0.5 && c.right <= window.innerWidth + 0.5 && c.bottom <= window.innerHeight + 0.5,
    cardOpaque: getComputedStyle(card).opacity === "1" && c.width > 40 && c.height > 40,
    textClipped:
      document.getElementById("tour-text").scrollHeight > document.getElementById("tour-text").clientHeight + 1 ||
      card.scrollHeight > card.clientHeight + 1,
    focus: document.activeElement ? document.activeElement.id : "",
    index: openTour.inspect.run.index,
    total: openTour.inspect.run.steps.length,
    wantTab: step.tab || "",
    tab: openTour.inspect.activeTab(),
    notesShown,
    busy: card.getAttribute("aria-busy") === "true",
    // Chaining (the owner, 2026-09-23): the count is per section, and the
    // last card of a section offers the next one by name.
    sectionId: (openTour.inspect.run.steps[openTour.inspect.run.index] || step).sectionId,
    sectionAt: openTour.inspect.place(openTour.inspect.run).at,
    sectionTotal: openTour.inspect.place(openTour.inspect.run).total,
    nextSection: openTour.inspect.place(openTour.inspect.run).next,
    last: openTour.inspect.run.index >= openTour.inspect.run.steps.length - 1,
    nextText: document.getElementById("tour-next").textContent,
    skipText: document.getElementById("tour-skip").textContent,
    wantSettings: step.settings || "",
    settingsShown: step.settings
      ? typeof settingsModalOpen === "function" && settingsModalOpen() &&
        Boolean(document.querySelector(`#settings-nav button.active[data-section="${step.settings}"]`))
      : !(typeof settingsModalOpen === "function" && settingsModalOpen()),
    wantWb: step.wb || "",
    orText: step.orText || "",
    ownText: step.text,
    wbFace: (() => {
      const canvasView = document.getElementById("wb-canvas-view");
      if (!canvasView || canvasView.classList.contains("hidden") || !canvasView.getClientRects().length) return "landing";
      return typeof wbIsMap === "function" && wbIsMap() ? "map" : "board";
    })(),
  };
};

// Wait until the walk in progress has drawn its card (the busy flag is set
// while a step navigates and waits for its control, and cleared when it is
// drawn), then a frame more for the placement.
async function settled(page) {
  await page.waitForFunction(
    () => !openTour.inspect.run || document.getElementById("tour-card").getAttribute("aria-busy") !== "true",
    null,
    { timeout: 8000 }
  );
  //: Two frames for the placement, not a fixed 120 ms: the card has no transition on its box.
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
}

// Every check a step must pass. Returns whether all did.
function judge(label, m, phone) {
  const tag = `${label} ${m.counter} ${m.target}${m.alt ? `->${m.shownTarget}` : ""}`;
  let ok = true;
  ok = check(!m.stranded, `${tag} is not stranded (it has a control to point at)`) && ok;
  ok = check(m.exists && m.laidOut, `${tag} target exists and is laid out ${JSON.stringify(m.anchor)}`) && ok;
  ok = check(m.inWindow, `${tag} target is inside the window ${JSON.stringify(m.anchor)} in ${m.vw}x${m.vh}`) && ok;
  ok = check(!m.covered, `${tag} nothing is drawn over the target (${m.coveredBy.join(",") || "clear"})`) && ok;
  ok = check(!m.spotHidden && m.spotCovers, `${tag} the cut-out sits on the target spot=${JSON.stringify(m.spot)}`) && ok;
  ok = check(m.cardInside && m.cardOpaque, `${tag} the card is on screen ${JSON.stringify(m.card)}`) && ok;
  ok = check(m.overlap === 0 && m.gap >= 8, `${tag} the card is clear of the target (overlap ${m.overlap}, gap ${m.gap})`) && ok;
  ok = check(!m.textClipped, `${tag} no clipped text`) && ok;
  ok = check(!m.wantTab || m.tab === m.wantTab, `${tag} the ${m.wantTab || "current"} tab is showing (${m.tab})`) && ok;
  ok = check(m.notesShown, `${tag} its Notes sub-tab is showing`) && ok;
  ok = check(
    m.counter === `${m.sectionAt + 1} of ${m.sectionTotal}`,
    `${tag} counter is per section (${m.counter}, step ${m.sectionAt + 1} of ${m.sectionTotal} in ${m.section})`
  ) && ok;
  const wantNext = m.nextSection ? `Next: ${m.nextSection}` : m.last ? "Done" : "Next";
  const wantSkip = m.nextSection ? "Finish" : "Skip";
  ok = check(
    m.nextText === wantNext && m.skipText === wantSkip,
    `${tag} buttons read "${m.skipText}" / "${m.nextText}" (want "${wantSkip}" / "${wantNext}")`
  ) && ok;
  ok = check(m.settingsShown, `${tag} Settings is ${m.wantSettings ? `open at ${m.wantSettings}` : "closed"}`) && ok;
  if (m.wantWb) ok = check(m.wbFace === m.wantWb, `${tag} the boards sub-tab shows ${m.wantWb} (${m.wbFace})`) && ok;
  ok = check(m.focus === "tour-next", `${tag} focus is on Next (${m.focus})`) && ok;
  if (m.alt) ok = check(m.text === m.orText && m.orText !== m.ownText, `${tag} the card says where the control went: "${m.text}"`) && ok;
  ok = check(m.text.length <= 140, `${tag} short words (${m.text.length} chars)`) && ok;
  if (phone) {
    // A sheet: the window's width less its gutters, docked to an edge.
    const docked = m.card[1] <= 20 || m.card[1] + m.card[3] >= m.vh - 20;
    ok = check(m.card[2] >= m.vw - 40 && docked, `${tag} the card is a docked sheet (${m.side})`) && ok;
  }
  stepsSeen += 1;
  if (ok) stepsPassed += 1;
  return ok;
}

// Walk a run card by card, pressing Next, and judge every card. With
// `oneSection`, stop at the last card of the first section and press Finish
// there instead, which is how a section is played on its own.
async function walk(page, label, phone, { oneSection = false } = {}) {
  const seen = [];
  for (let guard = 0; guard < 90; guard += 1) {
    if (!(await page.evaluate(() => !!openTour.inspect.run))) break;
    await settled(page);
    if (!(await page.evaluate(() => !!openTour.inspect.run))) break;
    const m = await page.evaluate(STEP_PROBE);
    seen.push(m);
    console.log(
      `${label} ${m.section.padEnd(11)} ${m.counter.padEnd(7)} ${m.target.slice(0, 26).padEnd(26)} shown=${m.shownTarget.slice(0, 22).padEnd(22)} ` +
        `tab=${m.tab.padEnd(9)} side=${(m.side || "").padEnd(11)} card=${JSON.stringify(m.card)} anchor=${JSON.stringify(m.anchor)}`
    );
    judge(label, m, phone);
    if (oneSection && m.nextSection) {
      await page.click("#tour-skip");
      await closed(page);
      check(
        await page.evaluate(() => !openTour.inspect.run && localStorage.getItem("tourDone") === "1"),
        `${label} Finish at the end of ${m.section} ends the tour`
      );
      break;
    }
    //: No wait after the press: the click runs `openTour.inspect.tourNext`, which sets the card busy before it
    //: returns, and `settled` at the top of the loop waits for that flag to clear.
    await page.click("#tour-next");
  }
  // Per section: the total never changes, and it is the number of cards shown.
  const bySection = new Map();
  for (const m of seen) {
    if (!bySection.has(m.sectionId)) bySection.set(m.sectionId, []);
    bySection.get(m.sectionId).push(m);
  }
  for (const [id, cards] of bySection) {
    const totals = cards.map((c) => c.sectionTotal);
    check(
      totals.every((t) => t === cards.length),
      `${label} ${id}: the count's total never changes and is the cards shown (${totals.join("/")}, ${cards.length} shown)`
    );
  }
  // Sections are played in table order, each once, with no jump back.
  const table = await page.evaluate(() => openTour.inspect.sections.map((s) => s.id));
  const order = [...bySection.keys()];
  check(
    seen.every((m, i) => i === 0 || table.indexOf(m.sectionId) >= table.indexOf(seen[i - 1].sectionId)),
    `${label} sections play in order (${order.join(" > ")})`
  );
  if (!oneSection) {
    check(
      await page.evaluate(() => !openTour.inspect.run && document.getElementById("tour-card").classList.contains("hidden")),
      `${label} Done closes the tour`
    );
  }
  return seen;
}

// What each section plans at this window size (a `media` step belongs to
// one side of a breakpoint), against what a walk showed.
async function sectionReport(page, label, seen) {
  const planned = await page.evaluate(() =>
    openTour.inspect.sections.map((s) => ({
      id: s.id,
      targets: s.steps.filter((x) => !x.media || window.matchMedia(x.media).matches).map((x) => x.target),
    }))
  );
  const rows = [];
  for (const section of planned) {
    const shown = seen.filter((m) => m.sectionId === section.id).map((m) => m.target);
    const dropped = section.targets.filter((t) => !shown.includes(t));
    rows.push(`${section.id} ${shown.length}/${section.targets.length}${dropped.length ? ` dropped ${JSON.stringify(dropped)}` : ""}`);
  }
  console.log(`${label} per section, shown/planned: ${rows.join("; ")}`);
  return planned;
}

// "WxH" or "WxH@scale" (deviceScaleFactor), comma separated.
const SIZES = (process.env.SIZES || "1440x900,1184x760,390x844,1600x890@1.25")
  .split(",")
  .map((s) => {
    const [dims, scale] = s.split("@");
    return [...dims.split("x").map(Number), Number(scale || 1)];
  });

(async () => {
  for (const [width, height, scale] of SIZES) {
    const phone = width < 600;
    const { browser, page } = await boot({
      viewport: { width, height },
      isMobile: phone,
      hasTouch: phone,
      deviceScaleFactor: scale,
    });
    const label = `${width}x${height}${scale !== 1 ? `@${scale}` : ""}`;
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));

    //: tour.js is lazy: until it loads, openTour and TOUR_ENABLED are app.js stand-ins.
    await page.evaluate(() => ensureModule("tour"));
    // --- every door is live --------------------------------------------------
    // Settings is built when it is first opened, so its Help panel (the replay rows, the
    // "Start the tour" button, About's button) is opened first, as a person would reach it.
    await openHelp(page);
    const doors = await page.evaluate(() => {
      renderTourReplay();
      const replay = [...document.querySelectorAll("#tour-replay-buttons button")];
      const about = document.getElementById("about-take-tour");
      return {
        enabled: typeof TOUR_ENABLED !== "undefined" && TOUR_ENABLED,
        replay: replay.length,
        startDisabled: (document.getElementById("tour-start-btn") || { disabled: true }).disabled,
        replayDisabled: replay.filter((b) => b.disabled).length,
        about: Boolean(about),
        aboutDisabled: Boolean(about && about.disabled),
      };
    });
    console.log(`${label} doors: ${JSON.stringify(doors)}`);
    check(doors.enabled, `${label} TOUR_ENABLED is on`);
    const sectionCount = await page.evaluate(() => openTour.inspect.sections.length);
    check(
      // One row per section, and "Start the tour" is its own button above them (INBOX 804).
      doors.replay === sectionCount && doors.replayDisabled === 0 && !doors.startDisabled,
      `${label} the ${sectionCount} replay rows and the start button are live (${doors.replay})`
    );
    check(doors.about && !doors.aboutDisabled, `${label} About's take-the-tour button is live`);
    await page.evaluate(() => closeSettingsModal());
    await page.waitForFunction(() => !settingsModalOpen(), null, { timeout: 8000 });

    // What the notebook holds before any tour runs: the tour may open a
    // board or a map, and must never make one (or anything else).
    const holdings = () =>
      page.evaluate(async () => {
        const boards = await apiJson("/whiteboard/boards", { silent: true }).catch(() => []);
        const entries = await apiJson("/entries/count", { silent: true }).catch(() => null);
        return JSON.stringify({ boards: boards.length, entries });
      });
    const before = await holdings();

    // --- the welcome's hand-off ----------------------------------------------
    await page.evaluate(() => {
      localStorage.removeItem("onboardingDone");
      localStorage.removeItem("tourDone");
    });
    await goTab(page, "dashboard");
    // showOnboarding, not openOnboarding: the latter now queues the welcome behind the first-run turns (firstRunTurn)
    // and waits for a clear screen, so the sweep's next click waited on a card that had not been drawn.
    await page.evaluate(() => showOnboarding());
    await page.waitForSelector("#onboarding-next", { state: "visible" });
    const slides = await page.evaluate(() => ONBOARDING_SLIDES.length);
    for (let slide = 0; slide < slides - 1; slide += 1) {
      await page.click("#onboarding-next");
      await frames(page);
    }
    check(
      (await page.textContent("#onboarding-next")).trim() === "Start the tour",
      `${label} the welcome's last button says Start the tour`
    );
    await page.click("#onboarding-next");
    await page.waitForFunction(() => !!openTour.inspect.run, null, { timeout: 8000 }).catch(() => {});
    check(await page.evaluate(() => !!openTour.inspect.run), `${label} the welcome's last button starts the tour`);
    // The welcome hands over to the basics, and the basics chain on through
    // every section to the end.
    const fromWelcome = await walk(page, `${label} welcome`, phone);
    await sectionReport(page, `${label} welcome`, fromWelcome);

    lap("welcome walk done");
    // --- every section on its own, ending with Finish -------------------------
    const sections = await page.evaluate(() => openTour.inspect.sections.map((s) => s.id));
    for (const section of sections) {
      await goTab(page, "dashboard");
      await page.evaluate((id) => openTour(id), section);
      const one = await walk(page, `${label} ${section}`, phone, { oneSection: section !== sections[sections.length - 1] });
      if (one.length) {
        check(one[0].sectionId === section, `${label} ${section}'s button starts at ${section} (${one[0].sectionId})`);
      }
    }

    lap("sections on their own done");
    // --- Next: <section> goes straight on; Back comes straight back ----------
    await page.evaluate(() => openTour("notes"));
    await settled(page);
    const first = await page.evaluate(STEP_PROBE);
    check(first.sectionId === "notes" && first.sectionAt === 0, `${label} a section's button opens its first card`);
    for (let i = 0; i < 12; i += 1) {
      const m = await page.evaluate(STEP_PROBE);
      if (m.nextSection) break;
      await page.click("#tour-next");
      await settled(page);
    }
    const boundary = await page.evaluate(STEP_PROBE);
    await page.click("#tour-next");
    await settled(page);
    const into = await page.evaluate(STEP_PROBE);
    check(
      into.sectionId === "chat" && into.sectionAt === 0 && into.section === boundary.nextSection,
      `${label} "${boundary.nextText}" goes straight into ${into.section}, card ${into.counter}`
    );
    await page.click("#tour-back");
    await settled(page);
    const back = await page.evaluate(STEP_PROBE);
    check(
      back.sectionId === "notes" && back.target === boundary.target,
      `${label} Back from Chat's first card returns to Notes' last (${back.section} ${back.counter})`
    );
    await page.evaluate(() => openTour.inspect.close(false));

    // --- the whole tour from Settings' Start the tour -------------------------
    if (process.env.FULL !== "0") {
      await goTab(page, "reminders");
      await openHelp(page);
      await page.evaluate(() =>
        document.getElementById("tour-start-btn").click()
      );
      await page.waitForFunction(() => !!openTour.inspect.run, null, { timeout: 8000 });
      const whole = await walk(page, `${label} start the tour`, phone);
      await sectionReport(page, `${label} start the tour`, whole);
      check(
        JSON.stringify(whole.map((m) => m.target)) === JSON.stringify(fromWelcome.map((m) => m.target)),
        `${label} Start the tour and the welcome walk the same cards (${whole.length} and ${fromWelcome.length})`
      );
    }
    check(
      await page.evaluate(() => localStorage.getItem("tourDone") === "1"),
      `${label} finishing is remembered (tourDone)`
    );

    lap("start-the-tour walk done");
    // --- with an overlay open, the tour closes it first ----------------------
    for (const opener of ["openHelpChat()", "openPalette()", "openFeatures()", "openShortcuts()"]) {
      await page.evaluate((src) => new Function(src)(), opener);
      await page.waitForTimeout(700);
      await page.evaluate(() => openTour("basics"));
      await settled(page);
      const m = await page.evaluate(STEP_PROBE);
      //: A sheet is closed when it has left, and its exit animation is still running two frames after the
      //: tour closed it (390, the Atlas guide: `sheet-leaving`). Waited for; one that never leaves still fails below.
      const openDialogs = () =>
        [...document.querySelectorAll('[role="dialog"][aria-modal="true"]')]
          .filter((el) => el.id !== "tour-card" && !el.classList.contains("hidden") && el.getClientRects().length)
          .map((el) => el.id || el.className);
      await page.waitForFunction(`(${openDialogs})().length === 0`, null, { timeout: 2000 }).catch(() => {});
      const open = await page.evaluate(openDialogs);
      judge(`${label} over ${opener}`, m, phone);
      check(open.length === 0, `${label} ${opener} was closed by the tour (${JSON.stringify(open)})`);
      await page.evaluate(() => openTour.inspect.close(false));
      await page.waitForTimeout(200);
    }

    lap("overlays done");
    // --- a resize across the phone breakpoint, mid-step ----------------------
    if (!phone) {
      await page.evaluate(() => openTour("basics"));
      for (let i = 0; i < 3; i += 1) {
        await settled(page);
        await page.click("#tour-next");
      }
      await settled(page);
      await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(600);
      const narrow = await page.evaluate(STEP_PROBE);
      console.log(`${label} resized to 390: showing ${narrow.shownTarget} card=${JSON.stringify(narrow.card)}`);
      check(narrow.shownTarget === "#phone-more-btn" && narrow.alt, `${label} at 390 the Settings step moves to More`);
      check(narrow.cardInside && narrow.overlap === 0 && !narrow.covered, `${label} at 390 the card is on screen and clear`);
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(600);
      const wide = await page.evaluate(STEP_PROBE);
      check(wide.shownTarget === "#settings-btn" && !wide.alt, `${label} back at ${width} it points at the gear again`);
      check(wide.cardInside && wide.overlap === 0 && wide.spotCovers, `${label} back at ${width} the card and cut-out follow`);
      await page.evaluate(() => openTour.inspect.close(false));
    }

    // --- typing in the lit control is typing ---------------------------------
    await page.evaluate(() => openTour("notes"));
    await settled(page);
    await page.click("#entry-content");
    await page.keyboard.type("ab");
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("Enter");
    const typed = await page.evaluate(() => ({
      index: openTour.inspect.run && openTour.inspect.run.index,
      value: document.getElementById("entry-content").value,
    }));
    check(typed.index === 0 && typed.value === "a\nb", `${label} arrows and Enter in the lit box edit it (${JSON.stringify(typed)})`);
    await page.evaluate(() => {
      document.getElementById("entry-content").value = "";
      document.getElementById("tour-next").focus();
    });
    await page.keyboard.press("ArrowRight");
    await settled(page);
    check(await page.evaluate(() => openTour.inspect.run && openTour.inspect.run.index === 1), `${label} ArrowRight on the card moves the tour on`);
    await page.keyboard.press("Escape");
    await closed(page);
    check(await page.evaluate(() => !openTour.inspect.run), `${label} Escape ends the tour`);

    // --- Next twice while a tab loads ----------------------------------------
    await goTab(page, "dashboard");
    await page.evaluate(() => openTour("notes"));
    await settled(page);
    await page.evaluate(() => {
      openTour.inspect.next();
      openTour.inspect.next();
    });
    await settled(page);
    await page.waitForTimeout(400);
    const twice = await page.evaluate(STEP_PROBE);
    check(twice.index === 2 && twice.counter === `3 of ${twice.sectionTotal}`, `${label} two quick Nexts land on step 3 once (${twice.counter})`);
    judge(`${label} after two quick Nexts`, twice, phone);
    await page.evaluate(() => openTour.inspect.close(false));

    // --- Back, Skip, the X, the Tab trap, focus handed back -------------------
    await page.evaluate(() => openTour("basics"));
    await settled(page);
    check(await page.evaluate(() => document.getElementById("tour-back").disabled), `${label} Back is disabled on the first step`);
    const tabbed = [];
    for (let i = 0; i < 6; i += 1) {
      await page.keyboard.press("Tab");
      tabbed.push(await page.evaluate(() => document.getElementById("tour-card").contains(document.activeElement)));
    }
    check(tabbed.every(Boolean), `${label} Tab stays inside the card`);
    await page.evaluate(() => document.getElementById("tour-next").focus());
    await page.click("#tour-next");
    await settled(page);
    await page.click("#tour-next");
    await settled(page);
    await page.click("#tour-back");
    await settled(page);
    check(await page.evaluate(() => openTour.inspect.run.index === 1), `${label} Back goes one step back`);
    await page.click("#tour-skip");
    await closed(page);
    check(
      await page.evaluate(
        () =>
          !openTour.inspect.run &&
          ["tour-card", "tour-spot", "tour-block"].every((id) => document.getElementById(id).classList.contains("hidden"))
      ),
      `${label} Skip closes the tour and its dim`
    );
    await page.evaluate(() => {
      document.getElementById("space-switcher-btn").focus();
      openTour("basics");
    });
    await settled(page);
    await page.click("#tour-close");
    await closed(page);
    const afterClose = await page.evaluate(() => ({ open: !!openTour.inspect.run, focus: document.activeElement?.id }));
    check(!afterClose.open && afterClose.focus === "space-switcher-btn", `${label} the X closes it and focus returns to the opener (${afterClose.focus})`);

    // --- a control hidden for good is left out before the count --------------
    const hidden = await page.evaluate(async () => {
      const el = document.getElementById("space-switcher-btn");
      el.style.display = "none";
      openTour("basics");
      const first = openTour.inspect.run.steps.filter((x) => x.sectionId === "basics").length;
      el.style.display = "";
      return first;
    });
    await settled(page);
    await page.evaluate(() => openTour.inspect.close(false));
    check(hidden === 3, `${label} a hidden chrome control is left out before the count (3, got ${hidden})`);

    // --- a notebook with no mind map: pointed at New mind map, nothing made --
    await page.evaluate(() => {
      window.__tourNeedsMap = openTour.inspect.needs.map;
      openTour.inspect.needs.map = () => false;
    });
    await goTab(page, "dashboard");
    await page.evaluate(() => openTour("maps"));
    await settled(page);
    const noMap = await page.evaluate(STEP_PROBE);
    judge(`${label} no map`, noMap, phone);
    check(
      noMap.sectionId === "maps" && noMap.sectionTotal === 1 && /New's arrow, then Mind map/.test(noMap.text) && noMap.wbFace === "landing",
      `${label} with no map, Mind maps is one card on New mind map (${noMap.counter}, ${noMap.shownTarget}, ${noMap.wbFace})`
    );
    await page.evaluate(() => {
      openTour.inspect.close(false);
      openTour.inspect.needs.map = window.__tourNeedsMap;
    });
    const after = await holdings();
    check(after === before, `${label} the tours made nothing (before ${before}, after ${after})`);

    lap("no-map done");
    // --- the dim is on the page and not on the lit control -------------------
    await goTab(page, "dashboard");
    const points = await page.evaluate(() => {
      const bar = document.getElementById("space-switcher-btn").getBoundingClientRect();
      return {
        bright: [Math.round(bar.left + bar.width / 2), Math.round(bar.top + bar.height / 2)],
        dim: [Math.round(window.innerWidth / 2), Math.round(window.innerHeight / 2)],
      };
    });
    const plain = `${SHOTS}/${label}-plain.png`;
    const dimmed = `${SHOTS}/${label}-tour.png`;
    await page.screenshot({ path: plain });
    await page.evaluate(() => openTour("basics"));
    await settled(page);
    await page.click("#tour-next");
    await settled(page);
    // The card is somewhere; the page point is moved off it if it landed there.
    const cardBox = await page.evaluate(() => document.getElementById("tour-card").getBoundingClientRect().toJSON());
    if (points.dim[0] >= cardBox.left && points.dim[0] <= cardBox.right && points.dim[1] >= cardBox.top && points.dim[1] <= cardBox.bottom) {
      points.dim[1] = cardBox.top > height / 2 ? Math.round(cardBox.top / 2) : Math.round((cardBox.bottom + height) / 2);
    }
    await page.screenshot({ path: dimmed });
    await page.evaluate(() => openTour.inspect.close(false));
    const pixel = (file, [x, y]) =>
      execFileSync("python3", [path.join(ROOT, "scratchpad/pngpixel.py"), file, String(Math.round(x * scale)), String(Math.round(y * scale))], {
        encoding: "utf-8",
      }).trim();
    const lum = (line) => {
      const m = line.match(/\((\d+),\s*(\d+),\s*(\d+)/);
      return m ? (Number(m[1]) + Number(m[2]) + Number(m[3])) / 3 : NaN;
    };
    const b0 = lum(pixel(plain, points.bright));
    const b1 = lum(pixel(dimmed, points.bright));
    const d0 = lum(pixel(plain, points.dim));
    const d1 = lum(pixel(dimmed, points.dim));
    check(Math.abs(b0 - b1) < 3, `${label} the lit control is not dimmed (${b0} -> ${b1})`);
    check(d1 <= d0 * 0.8, `${label} the page around it is dimmed (${d0} -> ${d1})`);

    // --- the replay strip plays one section, with Settings out of the way ----
    await openHelp(page);
    await page.evaluate(() =>
      [...document.querySelectorAll("#tour-replay-buttons button")].find((b) => b.querySelector(".tour-row-name")?.textContent === "Graph").click()
    );
    await page.waitForFunction(() => !!openTour.inspect.run, null, { timeout: 8000 });
    await settled(page);
    const fromSettings = await page.evaluate(() => ({
      open: !!openTour.inspect.run,
      settingsOpen: !document.getElementById("settings-modal").classList.contains("hidden"),
      section: document.getElementById("tour-section").textContent,
    }));
    check(fromSettings.open && fromSettings.section === "Graph", `${label} a section button plays that section`);
    check(!fromSettings.settingsOpen, `${label} the settings modal is out of the way first`);
    judge(`${label} from Settings`, await page.evaluate(STEP_PROBE), phone);
    await page.evaluate(() => openTour.inspect.close(false));

    lap("replay strip done");
    // --- the card's text as rendered ------------------------------------------
    await page.evaluate(() => openTour("basics"));
    await settled(page);
    const inkShot = `${SHOTS}/${label}-card.png`;
    await page.screenshot({ path: inkShot });
    const inkBoxes = await page.evaluate(() => {
      const out = {};
      for (const id of ["tour-title", "tour-text", "tour-count", "tour-section"]) {
        const box = document.getElementById(id).getBoundingClientRect();
        out[id] = [Math.round(box.left), Math.round(box.top), Math.max(1, Math.round(box.width)), Math.max(1, Math.round(box.height))];
      }
      return out;
    });
    await page.evaluate(() => openTour.inspect.close(false));
    const ink = {};
    for (const [id, box] of Object.entries(inkBoxes)) {
      ink[id] = Number(
        execFileSync("python3", [path.join(__dirname, "rectcontrast.py"), inkShot, ...box.map((v) => String(Math.round(v * scale)))], {
          encoding: "utf-8",
        }).trim()
      );
    }
    check(Object.values(ink).every((r) => r >= 4.5), `${label} the card's text is at least 4.5:1 as rendered ${JSON.stringify(ink)}`);

    check(errors.length === 0, `${label} no page errors (${errors.join("; ")})`);
    await browser.close();
  }

  console.log(`\nsteps: ${stepsPassed} of ${stepsSeen} passed every check`);
  console.log(failures.length ? `${failures.length} FAILURES:\n  ` + failures.join("\n  ") : "all checks passed");
  process.exit(failures.length ? 1 : 0);
})();
