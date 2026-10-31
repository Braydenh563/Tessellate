// The document editor, measured in a real Chromium against a running app:
// the selection toolbar (PLAN.md §2 D2), undo and redo through one editor
// history (D3's acceptance), Phase 0's click-an-underline suggestions, the
// findings chip and panel, and the line-number column.
//
// **Re-pointed 2026-10-05 at the CodeMirror editor.** The sweep was written for
// the textarea editor: a `<textarea id="doc-content">`, a hand-rolled undo
// stack (`docUndoStack`), a backdrop of `<mark>`s behind the text, a Live view
// of one `.lp-src` box per paragraph and a `.doc-gutter` column. All of that is
// gone (DOCUMENTS_PLAN Phase 8), so every read now goes through `docSurface()`
// (the adapter with the textarea's own interface over the view) and the marks
// are `.cm-finding[data-doc-finding]` inside `.cm-content`. Of the old 89
// checks, 78 remain (all passing at 1440). Retired, not ported: the backdrop's
// own geometry and ink, D3's stack depth, cap and coalesce constants, Live's
// per-paragraph boxes, the backdrop's switch-off in Live and in a code file,
// and the textarea gutter's padding and font-size match (since INBOX 590 the
// numbers are smaller on purpose, so baselines are compared instead; the
// documents editor's own column is measured against the engine's `coordsAt`).
// Found while porting: Playwright's `Control+Shift+z` sends `event.key === "z"`,
// which CodeMirror reads as Ctrl+Z, so redo is pressed as `Control+Shift+Z`.
//
//   BASE=http://127.0.0.1:8802 SCRATCH=/tmp/mm-small-sc \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/editor.js
//
// Every assertion here is a *number* read out of the page, not a screenshot
// looked at — CLAUDE.md's rule, and the reason the selection bar's "one frame"
// claim and the undo stack's "restores exactly the prior text and selection"
// claim are both checkable rather than asserted.
const { boot } = require("./lib.js");

const BODY = [
  "Alpha paragraph one.",
  "Beta paragraph two.",
  "Gamma paragraph three.",
  "Delta paragraph four.",
].join("\n\n");

let failures = 0;
let checks = 0;
function ok(name, condition, detail) {
  checks += 1;
  if (!condition) failures += 1;
  console.log(`${condition ? "PASS" : "FAIL"}  ${name}${detail === undefined ? "" : `  — ${detail}`}`);
}

(async () => {
  const { browser, page } = await boot();
  const consoleErrors = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text().slice(0, 200)));
  page.on("pageerror", (e) => consoleErrors.push("PAGEERROR " + e.message));

  // The documents code is a lazy bundle (the Library's): ask for it the way
  // the tab does before any of its functions are called.
  await page.evaluate(async () => {
    if (typeof ensureModule === "function") await ensureModule("library");
  });

  const makeDoc = (title, content) => page.evaluate(async ([t, c]) => {
    const r = await api("/documents", {
      method: "POST",
      body: JSON.stringify({ title: t, content: c, file_type: "md" }),
    });
    return await r.json();
  }, [title, content]);
  const openDoc = async (id, view = "source") => {
    await page.evaluate(async ([docId, mode]) => {
      switchTab("documents");
      await new Promise((r) => setTimeout(r, 400));
      await openDocument(docId);
      await new Promise((r) => setTimeout(r, 900));
      setDocView(mode);
    }, [id, view]);
    await page.waitForTimeout(700);
  };
  const doc = await makeDoc("Editor sweep", BODY);
  await openDoc(doc.id);
  const loaded = await page.evaluate(() => ({
    id: currentDoc && currentDoc.id,
    len: docSurface().text.length,
    kind: docSurface().kind,
  }));
  ok("document open in the editor", loaded.id === doc.id && loaded.len === BODY.length && loaded.kind === "codemirror",
    JSON.stringify(loaded));

  // Timing probe: a capture-phase listener stamps the moment the selection
  // changed, a bubble-phase one (registered after the app's own
  // `selectionBarSync`) stamps the moment the bar was visible. The gap is the
  // app's synchronous work, i.e. "within one frame" made into a number.
  await page.evaluate(() => {
    window.__t0 = null;
    window.__t1 = null;
    document.addEventListener("selectionchange", () => { window.__t0 = performance.now(); }, true);
    document.addEventListener("selectionchange", () => {
      const bar = document.getElementById("selection-bar");
      if (bar && !bar.classList.contains("hidden")) window.__t1 = performance.now();
    });
  });

  // ---------------------------------------------------------------- D2, Source
  // The selection is made through the surface (a CodeMirror transaction) and
  // the browser raises its own `selectionchange` for the DOM selection the
  // view then draws; a frame is waited for rather than one being synthesised,
  // so the timing below is the real path.
  const at = BODY.indexOf("Gamma");
  const select = (start, end) => page.evaluate(async ([from, to]) => {
    const s = docSurface();
    s.focus();
    s.setSelectionRange(from, to);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  }, [start, end]);
  await page.evaluate(() => { window.__t0 = null; window.__t1 = null; });
  await select(at, at + 5);
  const d2 = await page.evaluate(() => {
    const bar = document.getElementById("selection-bar");
    const rect = bar.getBoundingClientRect();
    const caret = editorCaretPoint(docSurface());
    const pane = document.getElementById("doc-panes").getBoundingClientRect();
    return {
      hidden: bar.classList.contains("hidden"),
      ms: window.__t1 === null || window.__t0 === null ? null : window.__t1 - window.__t0,
      barTop: rect.top,
      barLeft: rect.left,
      barRight: rect.right,
      selTop: caret.top,
      pane: { top: pane.top, left: pane.left, right: pane.right, bottom: pane.bottom },
      styleAttr: bar.getAttribute("style") || "",
      buttons: [...bar.querySelectorAll("button")]
        .filter((b) => !b.hidden)
        .map((b) => b.dataset.md || (b.dataset.inlineAi ? "ai:rewrite" : "ai:ask")),
    };
  });
  ok("D2 bar visible on a selection", !d2.hidden);
  ok("D2 bar appears within 50ms of the selection", d2.ms !== null && d2.ms < 50,
    `${d2.ms === null ? "not measured" : d2.ms.toFixed(2)}ms`);
  ok("D2 bar top is above the selection top", d2.barTop < d2.selTop,
    `bar ${d2.barTop.toFixed(1)} < selection ${d2.selTop.toFixed(1)}`);
  ok("D2 bar is clamped inside the editor pane",
    d2.barLeft >= d2.pane.left - 1 && d2.barRight <= d2.pane.right + 1,
    `bar ${d2.barLeft.toFixed(0)}..${d2.barRight.toFixed(0)} in pane ${d2.pane.left.toFixed(0)}..${d2.pane.right.toFixed(0)}`);
  // CSP: the position has to be written through the CSSOM. An inline `style=`
  // string is what a `style` *attribute* in the markup would look like; these
  // are set with `el.style.top = …`, which produces the same attribute — so
  // what is checked is that only geometry lives there, never a whole rule set.
  ok("D2 positions with CSSOM geometry only",
    /^\s*(top|left)\s*:[^;]+;?\s*(top|left)?\s*:?[^;]*;?\s*$/.test(d2.styleAttr),
    JSON.stringify(d2.styleAttr));
  const WANT = ["bold", "italic", "link", "h2", "quote", "code"];
  ok("D2 has bold/italic/link/heading/quote/code",
    WANT.every((k) => d2.buttons.includes(k)), JSON.stringify(d2.buttons));
  ok("D2 has an AI action", d2.buttons.some((b) => b.startsWith("ai:")),
    JSON.stringify(d2.buttons.filter((b) => b.startsWith("ai:"))));

  // Every button changes the text the way the fixed strip does. The strip's
  // delegated click handler calls `applyMarkdown(md, boxId)`; the floating bar
  // is driven here by a real mousedown on the real element, and the two results
  // are compared character for character. One edit path, proved rather than
  // read.
  for (const md of [...WANT, "strike", "highlight"]) {
    const same = await page.evaluate(async (key) => {
      const s = docSurface();
      const start = s.text.indexOf("Gamma");
      const reset = async (v) => {
        s.text = v;
        s.focus();
        s.setSelectionRange(start, start + 5);
        await new Promise((r) => requestAnimationFrame(r));
        document.dispatchEvent(new Event("selectionchange"));
      };
      const base = s.text;
      // The strip's path.
      await reset(base);
      applyMarkdown(key, "doc-content");
      const viaStrip = s.text;
      // The floating bar's path — a real mousedown on the real button.
      await reset(base);
      const button = document.querySelector(`#selection-bar button[data-md="${key}"]`);
      if (!button) return { missing: true };
      button.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      const viaBar = s.text;
      s.text = base;
      return { viaStrip, viaBar, changed: viaBar !== base };
    }, md);
    ok(`D2 "${md}" edits exactly as the strip does`,
      !same.missing && same.changed && same.viaBar === same.viaStrip,
      same.missing ? "no button" : JSON.stringify(same.viaBar.slice(
        Math.max(0, same.viaBar.indexOf("Gamma") - 4), same.viaBar.indexOf("Gamma") + 14)));
  }

  // Hide rules.
  const hide = await page.evaluate(async (start) => {
    const bar = document.getElementById("selection-bar");
    const s = docSurface();
    const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const show = async () => {
      s.focus();
      s.setSelectionRange(start, start + 5);
      await frame();
      document.dispatchEvent(new Event("selectionchange"));
    };
    await show();
    const shown = !bar.classList.contains("hidden");
    // Collapse.
    s.setSelectionRange(start, start);
    await frame();
    document.dispatchEvent(new Event("selectionchange"));
    const onCollapse = bar.classList.contains("hidden");
    // Escape.
    await show();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    const onEscape = bar.classList.contains("hidden");
    // Focus leaving the editor entirely.
    await show();
    document.getElementById("doc-title").focus();
    await frame();
    document.dispatchEvent(new Event("selectionchange"));
    const onBlur = bar.classList.contains("hidden");
    return { shown, onCollapse, onEscape, onBlur };
  }, at);
  ok("D2 hides on selection collapse", hide.shown && hide.onCollapse);
  ok("D2 hides on Escape", hide.onEscape);
  ok("D2 hides when focus leaves the editor", hide.onBlur);

  // ------------------------------------------------------------------ D2, Live
  // One editor in every view now, so Live is the same surface with the markers
  // hidden; the bar has to sit over a selection made there too, above it.
  await page.evaluate(() => setDocView("live"));
  await page.waitForTimeout(500);
  await select(BODY.indexOf("Beta"), BODY.indexOf("Beta") + 4);
  const liveBar = await page.evaluate(() => {
    const bar = document.getElementById("selection-bar");
    const rect = bar.getBoundingClientRect();
    return {
      view: docView,
      hidden: bar.classList.contains("hidden"),
      barTop: rect.top,
      selTop: editorCaretPoint(docSurface()).top,
    };
  });
  ok("D2 bar appears in the Live view too", liveBar.view === "live" && !liveBar.hidden, JSON.stringify(liveBar));
  ok("D2 Live bar sits above the selection", liveBar.barTop < liveBar.selTop,
    `${liveBar.barTop} < ${liveBar.selTop}`);

  // ---------------------------------------------------------------------- D3
  // The PLAN.md acceptance, driven with real keystrokes: type in Live, switch
  // to Source, Ctrl+Z undoes the Live edit. There is one history now (the
  // view's), which is what the hand-rolled stack existed to imitate, so this
  // passes by construction and is kept as the check that it still does.
  const text = () => page.evaluate(() => docSurface().text);
  const caretTo = (pos) => page.evaluate(async (p) => {
    const s = docSurface();
    s.focus();
    s.setSelectionRange(p, p);
    await new Promise((r) => requestAnimationFrame(r));
  }, pos);
  await page.evaluate(() => setDocView("live"));
  await page.waitForTimeout(400);
  const before = await text();
  await caretTo(before.indexOf("Beta"));
  await page.keyboard.type("ZZZ");
  await page.waitForTimeout(200);
  const afterLiveType = await text();
  ok("D3 typing in Live reached the document", afterLiveType.includes("ZZZBeta"),
    JSON.stringify(afterLiveType.slice(0, 60)));

  // Source is a way to edit, so it sits behind Edit's chevron (the menu a
  // person opens), not in the segment beside Read.
  await page.click("#doc-view-menu > summary");
  await page.click('#doc-view-menu button[data-doc-view="source"]');
  await page.waitForTimeout(400);
  await page.evaluate(() => docSurface().focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(300);
  const afterUndo = await text();
  ok("D3 ACCEPTANCE: type in Live, switch to Source, Ctrl+Z undoes the Live edit",
    afterUndo === before,
    afterUndo === before ? `${before.length} chars restored` : JSON.stringify(afterUndo.slice(0, 60)));

  // "Control+Shift+Z", capital: Playwright's lower-case "z" with Shift held
  // sends `event.key === "z"`, which CodeMirror's keymap reads as plain Ctrl+Z
  // (undo) before it ever tries the Shift binding. A real keyboard reports "Z".
  await page.keyboard.press("Control+Shift+Z");
  await page.waitForTimeout(250);
  const afterRedo = await text();
  ok("D3 Ctrl+Shift+Z redoes it", afterRedo === afterLiveType,
    JSON.stringify(afterRedo.slice(0, 40)));
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  await page.keyboard.press("Control+y");
  await page.waitForTimeout(250);
  const afterCtrlY = await text();
  ok("D3 Ctrl+Y redoes it too", afterCtrlY === afterLiveType);
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);

  // Undo after a toolbar action restores exactly the prior text *and* selection.
  const boldCase = await page.evaluate(async () => {
    const s = docSurface();
    const start = s.text.indexOf("Delta");
    s.focus();
    s.setSelectionRange(start, start + 5);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    document.dispatchEvent(new Event("selectionchange"));
    return { text: s.text, start, end: start + 5 };
  });
  await page.waitForTimeout(60);
  await page.evaluate(() => {
    document
      .querySelector('#selection-bar button[data-md="bold"]')
      .dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
  });
  await page.waitForTimeout(250);
  const bolded = await text();
  ok("D3 the Bold actually applied", bolded.includes("**Delta**"),
    JSON.stringify(bolded.slice(bolded.indexOf("Delta") - 6, bolded.indexOf("Delta") + 12)));
  await page.evaluate(() => docSurface().focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(300);
  const unbolded = await page.evaluate(() => {
    const s = docSurface();
    return { text: s.text, start: s.selectionStart, end: s.selectionEnd };
  });
  ok("D3 undo after Bold restores exactly the prior text",
    unbolded.text === boldCase.text,
    unbolded.text === boldCase.text ? "byte-identical" : JSON.stringify(unbolded.text.slice(0, 60)));
  ok("D3 undo after Bold restores exactly the prior selection",
    unbolded.start === boldCase.start && unbolded.end === boldCase.end,
    `got ${unbolded.start}..${unbolded.end}, wanted ${boldCase.start}..${boldCase.end}`);

  // Coalescing: a burst of typing is one undo step, a pause starts another.
  // Measured through the outcome (what one Ctrl+Z gives back), since the
  // history's depth is the library's business and is not exposed.
  const burstBase = await text();
  await caretTo(burstBase.length);
  await page.keyboard.type("abcdef", { delay: 20 });
  await page.waitForTimeout(200);
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  const afterBurstUndo = await text();
  ok("D3 a 6-character burst coalesces into one undo entry", afterBurstUndo === burstBase,
    `one Ctrl+Z restored the text: ${afterBurstUndo === burstBase}`);
  await page.keyboard.press("Control+y");
  await page.waitForTimeout(250);
  await page.waitForTimeout(700);
  await page.keyboard.type("gh");
  await page.waitForTimeout(150);
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  const afterPauseUndo = await text();
  ok("D3 typing after a >500ms pause starts a new entry",
    afterPauseUndo === `${burstBase}abcdef`,
    JSON.stringify(afterPauseUndo.slice(-12)));
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);

  // Undo works from inside Source as well as Live: an edit made and undone
  // inside one view gives back the same text.
  await page.evaluate(() => setDocView("source"));
  await page.waitForTimeout(400);
  const native = await text();
  await caretTo(0);
  await page.keyboard.type("QQ");
  await page.waitForTimeout(700);
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  ok("D3 Ctrl+Z inside Source undoes a Source edit", (await text()) === native);

  // Scrolling. The brief said "hide on scroll"; the bar instead **re-anchors**
  // to the caret (editor.js registers `selectionBarSync` on a capture-phase
  // scroll listener). That is strictly better — the selection is still there,
  // so the bar should still be over it — but "better" is a claim, so it is
  // measured: after scrolling the editor the bar must have moved by the same
  // amount the text did, not stayed where it was.
  const scrolled = await page.evaluate(async () => {
    const s = docSurface();
    const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    s.text = Array.from({ length: 120 }, (_, i) => `Line ${i} of a long document.`).join("\n\n");
    s.focus();
    s.scrollTop = 0;
    await frame();
    const start = s.text.indexOf("Line 20 ");
    s.setSelectionRange(start, start + 7);
    s.scrollTop = 0;
    await frame();
    document.dispatchEvent(new Event("selectionchange"));
    const bar = document.getElementById("selection-bar");
    const before = bar.getBoundingClientRect().top;
    const wasHidden = bar.classList.contains("hidden");
    const top0 = s.scrollTop;
    s.scrollTop = top0 + 200;
    await frame();
    return {
      wasHidden,
      before,
      moved: s.scrollTop - top0,
      after: bar.getBoundingClientRect().top,
      hiddenNow: bar.classList.contains("hidden"),
    };
  });
  ok("D2 re-anchors to the caret on scroll rather than drifting",
    !scrolled.wasHidden && !scrolled.hiddenNow && scrolled.moved > 0 &&
      Math.abs(scrolled.before - scrolled.after - scrolled.moved) < 3,
    `top ${scrolled.before.toFixed(0)} -> ${scrolled.after.toFixed(0)} for a ${scrolled.moved}px scroll`);

  // =========================================================================
  // DOCUMENTS_PLAN.md Phase 0: click an underline, see suggestions
  // =========================================================================
  //
  // Its own document, because the D2/D3 run above ends with 120 lines of
  // `Line N ...` written straight into the editor, with none of the offsets
  // the checks below need.
  const P0 = [
    "Alpha teh beta gamma.",
    "Gamma the the delta.",
    "A line with  double spaces and a seperate word.",
  ].join("\n\n");
  const p0doc = await makeDoc("Phase 0 sweep", P0);
  await openDoc(p0doc.id);
  await page.waitForTimeout(1200);

  // Typed rather than assigned where a check is about the whole path (input,
  // debounce, findings, marks); assigned where it only needs the text there.
  const setText = (value) => page.evaluate(async (content) => {
    docSurface().text = content;
    await new Promise((r) => setTimeout(r, 900));
  }, value);

  // The mark's own first box. A mark can be several boxes (a finding that
  // crosses a soft wrap), and the first is the one a click is aimed at.
  const markRect = (word) => page.evaluate((w) => {
    const mark = docFindingMarks().find((m) => m._docFinding.text === w);
    if (!mark) return null;
    const r = mark.getClientRects()[0];
    return { x: r.left + r.width / 2, y: r.top + r.height / 2, left: r.left, top: r.top, h: r.height };
  }, word);

  // --- 1. the marks --------------------------------------------------------
  // They are CodeMirror decorations now (a `<span class="cm-finding">` inside
  // the line), not `<mark>`s on a layer behind a transparent textarea, so the
  // alignment the backdrop had to earn by measurement is by construction. What
  // is still worth a number: they exist, they are inside the editor's own
  // content, and the three kinds still read differently.
  const back = await page.evaluate(() => {
    const marks = docFindingMarks().map((m) => {
      const style = getComputedStyle(m);
      return {
        text: m.textContent,
        cls: m.className,
        inContent: !!m.closest(".cm-content"),
        line: style.textDecorationLine,
        style: style.textDecorationStyle,
        colour: style.textDecorationColor,
      };
    });
    const content = document.querySelector(".cm-content");
    return { marks, ink: getComputedStyle(content).color, found: docProseFound.length };
  });
  ok("P0 every finding is drawn as a mark inside the editor's own content",
    back.marks.length === back.found && back.found === 4 && back.marks.every((m) => m.inContent),
    `${back.marks.length} marks for ${back.found} findings`);
  ok("P0 the text keeps its own ink (no transparent layer to look through)",
    back.ink !== "rgba(0, 0, 0, 0)", back.ink);
  const kinds = Object.fromEntries(back.marks.map((m) => [m.text, m]));
  // Chromium reports this as `color(srgb 0.69 0.10 0.10 / 0.8)`, which is
  // --error at 80%. Red is asserted as "much more red than green or blue"
  // rather than as a string, so a theme change cannot make this a lie.
  const redness = (c) => {
    const [r, g, b] = (c.match(/[\d.]+/g) || []).map(Number);
    return r > 0.5 && r > g * 2 && r > b * 2;
  };
  ok("P0 a misspelling is a red wavy underline",
    kinds.teh && kinds.teh.style === "wavy" && redness(kinds.teh.colour),
    kinds.teh && `${kinds.teh.style} ${kinds.teh.colour}`);
  ok("P0 a repeated word is dotted",
    kinds["the the"] && kinds["the the"].style === "dotted",
    kinds["the the"] && kinds["the the"].style);
  ok("P0 a style note is a blue wavy underline",
    kinds["  "] && kinds["  "].style === "wavy" && kinds["  "].cls.includes("cm-finding-style"),
    kinds["  "] && `${kinds["  "].style} ${kinds["  "].colour}`);

  // **The measurement that makes the marks worth trusting.** A mark that does
  // not sit exactly over the glyph it is about points at the wrong word, and
  // every click on it is then wrong too. `coordsAt` asks the engine where a
  // character is, independently of the decoration that wrapped it.
  const align = await page.evaluate(() => {
    const s = docSurface();
    const out = [];
    for (const mark of docFindingMarks()) {
      const finding = mark._docFinding;
      const point = s.coordsAt(finding.start);
      const rect = mark.getClientRects()[0];
      out.push({ text: finding.text, dx: rect.left - point.left, dy: rect.top - point.top });
    }
    return out;
  });
  ok("P0 every mark's box coincides with its glyph's box within 1px",
    align.length === 4 && align.every((a) => Math.abs(a.dx) <= 1 && Math.abs(a.dy) <= 1),
    align.map((a) => `${JSON.stringify(a.text)}: dx ${a.dx.toFixed(2)} dy ${a.dy.toFixed(2)}`).join(", "));

  // Scrolled, because a mark that is right at the top of the file and a line
  // out at the bottom is the failure mode a long document has.
  const scrolledBack = await page.evaluate(async () => {
    const s = docSurface();
    const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    s.text = `${Array.from({ length: 60 }, (_, i) => `Filler line ${i}.`).join("\n\n")}\n\nA seperate word down here.`;
    await new Promise((r) => setTimeout(r, 900));
    s.scrollTop = s.scrollHeight;
    await frame();
    await new Promise((r) => setTimeout(r, 400));
    const mark = docFindingMarks().find((m) => m._docFinding.text === "seperate");
    if (!mark) return { noMark: true, found: docProseFound.length, scrollTop: s.scrollTop };
    const finding = mark._docFinding;
    const point = s.coordsAt(finding.start);
    const rect = mark.getClientRects()[0];
    return { scrollTop: s.scrollTop, dx: rect.left - point.left, dy: rect.top - point.top };
  });
  ok("P0 a mark 60 paragraphs down is still within 1px of its glyph",
    !scrolledBack.noMark && Math.abs(scrolledBack.dx) <= 1 && Math.abs(scrolledBack.dy) <= 1,
    scrolledBack.noMark ? `no mark (${JSON.stringify(scrolledBack)})` :
      `scrollTop ${scrolledBack.scrollTop}, dx ${scrolledBack.dx.toFixed(2)} dy ${scrolledBack.dy.toFixed(2)}`);

  // ACCEPTANCE: type a misspelt word in Source, an underline appears within
  // 300ms. Measured from the keystroke to the frame the mark exists in, by
  // polling, not by waiting a fixed time and then looking.
  await setText("The quick brown fox. ");
  // The clock starts at the *last* keystroke of the word, stamped by a
  // listener inside the page. Starting it before `keyboard.type` would be
  // measuring Playwright's key dispatch as well as the app, and the claim
  // being made is about the pause after you finish a word.
  await page.evaluate(() => {
    const s = docSurface();
    s.focus();
    s.setSelectionRange(s.text.length, s.text.length);
    window.__lastKey = null;
    document.querySelector(".cm-content").addEventListener("keydown", () => { window.__lastKey = performance.now(); });
  });
  await page.keyboard.type("recieve");
  const underlineMs = await page.evaluate(async () => {
    for (let i = 0; i < 120; i += 1) {
      const hit = docFindingMarks().some((m) => m._docFinding.text === "recieve");
      if (hit) return performance.now() - window.__lastKey;
      await new Promise((r) => requestAnimationFrame(r));
    }
    return null;
  });
  ok("P0 ACCEPTANCE: a misspelt word is underlined within 300ms of typing it",
    underlineMs !== null && underlineMs < 300,
    underlineMs === null ? "never underlined" : `${underlineMs.toFixed(0)}ms`);

  // The marks are the editor's own, so they hold in every view that shows the
  // text (the backdrop's "off in Live" is retired with the backdrop).
  const inLive = await page.evaluate(async () => {
    setDocView("live");
    await new Promise((r) => setTimeout(r, 500));
    const live = docFindingMarks().length;
    setDocView("source");
    await new Promise((r) => setTimeout(r, 400));
    return { live, source: docFindingMarks().length };
  });
  ok("P0 the marks are drawn in the Live view as well as Source",
    inLive.live > 0 && inLive.live === inLive.source, JSON.stringify(inLive));

  // A code file has no prose findings, so it has no marks either. The type
  // can change under an open document, and `syncDocFileType` has to re-run the
  // prose pass: before it did, switching a markdown file to .py left squiggles
  // under words in code.
  await setText(P0);
  const typeSwitch = await page.evaluate(async () => {
    const read = () => ({
      ext: docFileType().ext,
      marks: docFindingMarks().length,
      findings: docProseFound.length,
    });
    const pick = async (ext) => {
      if (!docFileTypes.some((t) => t.ext === ext)) return null;
      await docTypeChoose(ext);
      await new Promise((r) => setTimeout(r, 1200));
      return read();
    };
    const before = read();
    const code = await pick("py");
    const back = await pick("md");
    return { before, code, back };
  });
  ok("P0 switching to a code file takes the marks away",
    typeSwitch.code && typeSwitch.code.marks === 0 && typeSwitch.code.findings === 0,
    JSON.stringify(typeSwitch.code));
  ok("P0 switching back to markdown restores them",
    typeSwitch.back && typeSwitch.back.marks === typeSwitch.before.marks &&
      typeSwitch.back.findings === typeSwitch.before.findings && typeSwitch.before.marks > 0,
    JSON.stringify(typeSwitch));

  // --- 2. one click opens the suggestions ----------------------------------
  // Back to the small document, so the whole path is the one under test.
  await setText(P0);

  // A real mouse click at the centre of the underline, not a synthesised
  // event on an element: the click has to land in the editor and be turned
  // back into a finding, which is the whole mechanism.
  const teh = await markRect("teh");
  await page.mouse.click(teh.x, teh.y);
  await page.waitForTimeout(250);
  const clicked = await page.evaluate(() => {
    const menu = document.getElementById("doc-suggest-menu");
    const first = menu.querySelector(".doc-suggest-item");
    return {
      open: !menu.classList.contains("hidden"),
      word: menu.querySelector(".doc-suggest-head .doc-finding-words")?.textContent,
      why: menu.querySelector(".doc-suggest-head .doc-finding-why")?.textContent,
      first: first?.textContent.trim(),
      // The caret stays in the text on a plain click, so typing carries on.
      focusIsMenu: menu.contains(document.activeElement),
      items: [...menu.querySelectorAll(".doc-suggest-item")].map((b) => b.textContent.trim()),
    };
  });
  ok("P0 ACCEPTANCE: one click on an underline opens the menu", clicked.open,
    JSON.stringify(clicked).slice(0, 160));
  ok("P0 the menu is about the word that was clicked", clicked.word === "teh", clicked.word);
  ok("P0 every finding carries a one-line why", !!clicked.why && clicked.why.length > 0,
    JSON.stringify(clicked.why));
  ok("P0 a plain click leaves the caret in the text", clicked.focusIsMenu === false);
  ok("P0 the menu offers 'Add to dictionary' and 'Ignore in this document'",
    clicked.items.some((t) => /Add .*to dictionary/.test(t)) &&
      clicked.items.some((t) => /Ignore in this document/.test(t)),
    JSON.stringify(clicked.items));

  // ACCEPTANCE: the first item replaces the word.
  const replaced = await page.evaluate(async () => {
    const before = docSurface().text;
    document.querySelector("#doc-suggest-menu .doc-suggest-item").click();
    await new Promise((r) => setTimeout(r, 400));
    return { before, after: docSurface().text };
  });
  ok("P0 ACCEPTANCE: the menu's first item replaces the word",
    replaced.before.includes("teh ") && replaced.after.includes("the beta") &&
      !replaced.after.includes("teh "),
    JSON.stringify(replaced.after.slice(0, 30)));

  // Ranked candidates: a word one edit from something the app knows gets that
  // word offered even though no rule has an answer for it.
  const ranked = await page.evaluate(() => {
    const near = docSuggestAlternatives({
      rule: "spelling", text: "enviroment", replacement: null, start: 0, end: 10,
    });
    const distances = [
      ["teh", "the", docEditDistance("teh", "the", 2)],
      ["recieve", "receive", docEditDistance("recieve", "receive", 2)],
      ["colour", "color", docEditDistance("colour", "color", 2)],
      ["alpha", "omega", docEditDistance("alpha", "omega", 2)],
    ];
    return { near, distances, cap: DOC_SUGGEST_MAX, pool: docKnownWords().length };
  });
  ok("P0 a transposition is one edit, a far word is over the cap",
    ranked.distances[0][2] === 1 && ranked.distances[1][2] === 1 &&
      ranked.distances[2][2] === 1 && ranked.distances[3][2] > 2,
    ranked.distances.map((d) => `${d[0]}/${d[1]}=${d[2]}`).join(" "));
  ok("P0 the nearest known word is offered even with no rule answer",
    ranked.near.includes("environment"), JSON.stringify(ranked.near));
  ok("P0 the candidate list is capped", ranked.near.length <= ranked.cap,
    `${ranked.near.length} of at most ${ranked.cap}, from a pool of ${ranked.pool}`);

  // ACCEPTANCE: F8 moves to the next finding.
  await setText(P0);
  const stepped = await page.evaluate(async () => {
    const s = docSurface();
    closeDocSuggest();
    s.focus();
    s.setSelectionRange(0, 0);
    await new Promise((r) => requestAnimationFrame(r));
    return { count: docProseFound.length, first: docProseFound[0].text };
  });
  await page.keyboard.press("F8");
  await page.waitForTimeout(300);
  const f8 = await page.evaluate(() => ({
    open: !document.getElementById("doc-suggest-menu").classList.contains("hidden"),
    on: docSuggestOpenFor && docSuggestOpenFor.text,
  }));
  await page.keyboard.press("F8");
  await page.waitForTimeout(300);
  const f8next = await page.evaluate(() => docSuggestOpenFor && docSuggestOpenFor.text);
  await page.keyboard.press("Shift+F8");
  await page.waitForTimeout(300);
  const f8back = await page.evaluate(() => docSuggestOpenFor && docSuggestOpenFor.text);
  ok("P0 ACCEPTANCE: F8 opens the first finding and moves to the next",
    f8.open && f8.on === stepped.first && f8next !== null && f8next !== f8.on,
    `${stepped.count} findings: ${f8.on} -> ${f8next}`);
  ok("P0 Shift+F8 steps back", f8back === f8.on, `${f8next} -> ${f8back}`);

  // Alt+Enter on a finding opens the same menu.
  const altEnter = await page.evaluate(async () => {
    closeDocSuggest();
    const s = docSurface();
    const finding = docProseFound[1];
    s.focus();
    s.setSelectionRange(finding.start + 1, finding.start + 1);
    await new Promise((r) => requestAnimationFrame(r));
    return finding.text;
  });
  await page.keyboard.press("Alt+Enter");
  await page.waitForTimeout(250);
  const altOpen = await page.evaluate(() => ({
    open: !document.getElementById("doc-suggest-menu").classList.contains("hidden"),
    on: docSuggestOpenFor && docSuggestOpenFor.text,
    focusIsMenu: document.getElementById("doc-suggest-menu").contains(document.activeElement),
  }));
  ok("P0 Alt+Enter on a finding opens its menu and takes the focus",
    altOpen.open && altOpen.on === altEnter && altOpen.focusIsMenu,
    JSON.stringify(altOpen));

  // Double-click and right-click still work, and the right-click path is the
  // one that was silently wrong before: a position read from the browser's own
  // caret API is per-line inside a textarea, so on line 3 it looked up the
  // wrong place entirely. Driven on a finding that is NOT on the first line.
  const laterLine = await page.evaluate(() => {
    closeDocSuggest();
    const mark = docFindingMarks().filter((m) => m._docFinding.start > 40).at(-1);
    const r = mark.getClientRects()[0];
    return { text: mark._docFinding.text, x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  await page.mouse.click(laterLine.x, laterLine.y, { button: "right" });
  await page.waitForTimeout(250);
  const rightClicked = await page.evaluate(() => ({
    open: !document.getElementById("doc-suggest-menu").classList.contains("hidden"),
    on: docSuggestOpenFor && docSuggestOpenFor.text,
  }));
  ok("P0 right-click opens the right finding on a line that is not the first",
    rightClicked.open && rightClicked.on === laterLine.text,
    `wanted ${laterLine.text}, got ${rightClicked.on}`);
  await page.evaluate(() => closeDocSuggest());
  await page.mouse.dblclick(laterLine.x, laterLine.y);
  await page.waitForTimeout(250);
  const doubleClicked = await page.evaluate(() => ({
    open: !document.getElementById("doc-suggest-menu").classList.contains("hidden"),
    on: docSuggestOpenFor && docSuggestOpenFor.text,
  }));
  ok("P0 double-click still opens the same menu",
    doubleClicked.open && doubleClicked.on === laterLine.text,
    JSON.stringify(doubleClicked));

  // ACCEPTANCE: the same click-to-suggest in the Live view.
  await page.evaluate(() => {
    closeDocSuggest();
    setDocView("live");
  });
  await page.waitForTimeout(700);
  const liveMark = await page.evaluate(() => {
    const mark = docFindingMarks().find((m) => m._docFinding.text === "teh" || m._docFinding.text === "the the");
    if (!mark) return { missing: true };
    const r = mark.getClientRects()[0];
    return { text: mark._docFinding.text, x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  if (!liveMark.missing) {
    await page.mouse.click(liveMark.x, liveMark.y);
    await page.waitForTimeout(300);
  }
  const liveOpen = await page.evaluate(() => ({
    open: !document.getElementById("doc-suggest-menu").classList.contains("hidden"),
    on: docSuggestOpenFor && docSuggestOpenFor.text,
  }));
  ok("P0 ACCEPTANCE: one click on a Live-view underline opens the menu too",
    !liveMark.missing && liveOpen.open && liveOpen.on === liveMark.text,
    liveMark.missing ? "no mark in Live" : `${liveMark.text} -> ${liveOpen.on}`);
  await page.evaluate(() => {
    closeDocSuggest();
    setDocView("source");
  });
  await page.waitForTimeout(400);

  // --- 3. the status bar count is a control --------------------------------
  const chip = await page.evaluate(() => {
    const el = document.getElementById("doc-prose");
    const style = getComputedStyle(el);
    return {
      tag: el.tagName,
      label: document.getElementById("doc-prose-count").textContent,
      controls: el.getAttribute("aria-controls"),
      chip: el.classList.contains("has-findings"),
      // A count with something behind it takes an edge and a wash; the empty
      // state stays flat, so the chip reads as pressable only when it is.
      border: style.borderColor,
      background: style.backgroundColor,
      // The switches are out of the bar and into the kebab, ids intact.
      switchesInBar: document.querySelectorAll("#doc-statusbar input[type=checkbox]").length,
      switchesInMenu: ["doc-autocorrect", "doc-complete"].filter(
        (id) => document.querySelector(`#doc-dock-menu #${id}`)).length,
      autocorrect: !!document.getElementById("doc-autocorrect"),
      complete: !!document.getElementById("doc-complete"),
    };
  });
  ok("P0 the findings count is a button with the panel as its target",
    chip.tag === "BUTTON" && chip.controls === "doc-prose-panel", JSON.stringify(chip.controls));
  ok("P0 a real count paints as a chip", chip.chip && chip.background !== "rgba(0, 0, 0, 0)",
    `${chip.label}: border ${chip.border}, background ${chip.background}`);
  ok("P0 the switches left the status bar for the kebab, ids intact",
    chip.switchesInBar === 0 && chip.switchesInMenu === 2 && chip.autocorrect && chip.complete,
    `bar ${chip.switchesInBar}, menu ${chip.switchesInMenu}`);

  // The switch still drives its preference, from its new home.
  const switched = await page.evaluate(() => {
    const box = document.getElementById("doc-autocorrect");
    const before = docToolPref("autocorrect", false);
    box.click();
    const after = docToolPref("autocorrect", false);
    box.click();
    return { before, after, restored: docToolPref("autocorrect", false) };
  });
  ok("P0 a switch in the kebab still writes its preference",
    switched.before !== switched.after && switched.restored === switched.before,
    JSON.stringify(switched));

  // ACCEPTANCE: the chip opens the panel, and the panel groups by kind.
  await page.click("#doc-prose");
  await page.waitForTimeout(300);
  const panel = await page.evaluate(() => {
    const el = document.getElementById("doc-prose-panel");
    const groups = [...el.querySelectorAll(".doc-prose-group")].map((g) => ({
      label: g.firstChild.textContent,
      count: Number(g.querySelector(".doc-prose-group-count").textContent),
      rows: g.nextElementSibling ? g.nextElementSibling.querySelectorAll(".doc-prose-row").length : 0,
    }));
    return {
      open: !el.classList.contains("hidden"),
      expanded: document.getElementById("doc-prose").getAttribute("aria-expanded"),
      groups,
      total: docProseFound.length,
    };
  });
  ok("P0 ACCEPTANCE: the status chip opens the suggestions panel",
    panel.open && panel.expanded === "true", JSON.stringify({ open: panel.open, expanded: panel.expanded }));
  // The rows were centred: a `<button>` takes the app's global
  // `justify-content: center`, and the `text-align: left` beside it has
  // nothing to align on a flex container. Measured, a row starting at x=326
  // whose first word began at x=751.7. Since the panel redesign (INBOX 549) a
  // row opens with its kind mark, so "left" means the first word sits one mark
  // and a gap in (21px at 1440), and every row's words share one left edge.
  const rowAlign = await page.evaluate(() => {
    const rows = [...document.querySelectorAll(".doc-prose-jump")];
    return rows.map((jump) => ({
      rowLeft: jump.getBoundingClientRect().left,
      wordLeft: jump.querySelector(".doc-finding-words").getBoundingClientRect().left,
    }));
  });
  const wordLefts = new Set(rowAlign.map((r) => Math.round(r.wordLeft)));
  ok("P0 panel rows start at the left of the list, not the middle",
    rowAlign.length > 0 && rowAlign.every((r) => r.wordLeft - r.rowLeft < 32) && wordLefts.size === 1,
    rowAlign.map((r) => `row ${r.rowLeft.toFixed(0)}, first word ${r.wordLeft.toFixed(0)}`).join("; "));
  ok("P0 the panel groups findings by kind, with a count on each group",
    panel.groups.length >= 2 &&
      panel.groups.every((g) => g.count === g.rows && g.count > 0) &&
      panel.groups.reduce((n, g) => n + g.count, 0) === panel.total,
    panel.groups.map((g) => `${g.label} ${g.count}`).join(", "));
  await page.click("#doc-prose");
  await page.waitForTimeout(200);

  // =========================================================================
  // The line-number column, in all three editors
  // =========================================================================
  //
  // Reported with a screenshot: gutter rows 1..18 continuing below a textarea
  // that ended at row 11, and numbers out of step with the text. The check is
  // the one the report implies: put 30 lines in, compare the top of gutter row
  // N with where line N is actually drawn, scroll, and compare again.
  //
  // The documents editor draws its own column now (CodeMirror's
  // `.cm-lineNumbers`, inside the scroller, so it cannot outgrow or out-scroll
  // the text), and the two note boxes still carry the textarea's `.doc-gutter`.
  // So the documents' rows are compared with the engine's own `coordsAt` and
  // the textareas' with `docCaretPoint`, as before.
  const GUTTER_LINES = Array.from(
    { length: 30 }, (_, i) => `Line ${i + 1} of the document under test.`
  ).join("\n");

  // --- the documents editor
  const gutterDoc = await makeDoc("Gutter sweep", GUTTER_LINES);
  await page.evaluate(() => localStorage.setItem("doc-gutter", "1"));
  await openDoc(gutterDoc.id);
  await page.evaluate(() => setDocGutter(true));
  await page.waitForTimeout(900);
  const docGutter = () => page.evaluate(() => {
    const s = docSurface();
    const rows = [...document.querySelectorAll("#doc-panes .cm-lineNumbers .cm-gutterElement")]
      // CodeMirror keeps one hidden element per gutter holding the widest
      // number it expects; it is not a row.
      .filter((e) => e.textContent.trim() && getComputedStyle(e).visibility !== "hidden");
    if (!rows.length) return { missing: true };
    const lineTop = (n) => {
      const at = s.text.split("\n").slice(0, n - 1).join("\n").length + (n > 1 ? 1 : 0);
      return s.coordsAt(at).top;
    };
    const byNumber = Object.fromEntries(rows.map((e) => [e.textContent.trim(), e]));
    const picked = [1, 5, 11, 20, 30].filter((n) => byNumber[n]);
    // A constant offset is the font's leading (the glyph box sits inside the
    // line box); *drift* is what the report was, so the spread is measured.
    const deltas = picked.map((n) => ({ n, delta: byNumber[n].getBoundingClientRect().top - lineTop(n) }));
    const scroller = document.querySelector("#doc-panes .cm-scroller");
    const gutters = document.querySelector("#doc-panes .cm-gutters");
    return {
      rows: rows.length,
      deltas,
      spread: Math.max(...deltas.map((d) => d.delta)) - Math.min(...deltas.map((d) => d.delta)),
      worst: Math.max(...deltas.map((d) => Math.abs(d.delta))),
      inScroller: scroller.contains(gutters),
      scrollTop: scroller.scrollTop,
    };
  });
  const gd = await docGutter();
  ok("gutter (documents) draws a number for every line", !gd.missing && gd.rows === 30,
    gd.missing ? "no gutter" : `${gd.rows} rows`);
  ok("gutter (documents) lives inside the text's own scroller", !gd.missing && gd.inScroller);
  ok("gutter (documents) rows sit on their lines within 2px, with no drift",
    !gd.missing && gd.worst <= 2 && gd.spread <= 1,
    gd.missing ? "no gutter" : gd.deltas.map((r) => `${r.n}:${r.delta.toFixed(2)}`).join(" "));
  await page.evaluate(async () => {
    const s = docSurface();
    s.scrollTop = 200;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    await new Promise((r) => setTimeout(r, 300));
  });
  const gds = await docGutter();
  ok("gutter (documents, scrolled) rows still sit on their lines with no drift",
    !gds.missing && gds.scrollTop > 0 && gds.worst <= 2 && gds.spread <= 1,
    gds.missing ? "no gutter" : `scrollTop ${gds.scrollTop}: ${gds.deltas.map((r) => `${r.n}:${r.delta.toFixed(2)}`).join(" ")}`);

  //: Runs in the page, for a note box that is still a textarea. Each row's and
  //: each line's *baseline* is compared, not their tops: since INBOX 590 the
  //: numbers are deliberately smaller than the text (11.2px against 16px, on
  //: the text's baseline), so their boxes differ in height and only the
  //: baselines are meant to coincide. A baseline is the top of a run's content
  //: area plus its font's own ascent (`fontBoundingBoxAscent`), the metric the
  //: browser sizes that area with (`gutter.js` does the same). Row tops come
  //: from a Range over the number's own characters; line tops come from
  //: `docCaretPoint`, the app's independent measurement of where a character
  //: sits inside the textarea.
  const gutterMeasure = (boxId) => {
    const box = document.getElementById(boxId);
    const gutter = [...document.querySelectorAll(".doc-gutter")]
      .find((g) => (g.dataset.for ? g.dataset.for : "doc-content") === boxId);
    if (!gutter || gutter.classList.contains("hidden")) return { missing: true };
    const boxRect = box.getBoundingClientRect();
    const gutRect = gutter.getBoundingClientRect();
    const node = gutter.firstChild;
    const text = gutter.textContent;
    const cx = document.createElement("canvas").getContext("2d");
    const ascent = (el) => {
      const st = getComputedStyle(el);
      cx.font = `${st.fontStyle} ${st.fontWeight} ${st.fontSize} ${st.fontFamily}`;
      return cx.measureText("0123456789").fontBoundingBoxAscent;
    };
    const rowBase = (n) => {
      const start = text.split("\n").slice(0, n - 1).join("\n").length + (n > 1 ? 1 : 0);
      const range = document.createRange();
      range.setStart(node, start);
      range.setEnd(node, start + String(n).length);
      return range.getBoundingClientRect().top + ascent(gutter);
    };
    const lineBase = (n) => {
      const at = box.value.split("\n").slice(0, n - 1).join("\n").length + (n > 1 ? 1 : 0);
      // `docCaretPoint` asks a surface (the adapter over a textarea here).
      const surface = asSurface(box);
      surface.setSelectionRange(at, at);
      return docCaretPoint(surface).top + ascent(box);
    };
    const rows = [1, 5, 11, 20, 30].map((n) => ({ n, delta: rowBase(n) - lineBase(n) }));
    const style = getComputedStyle(gutter);
    const boxStyle = getComputedStyle(box);
    return {
      overflow: gutRect.bottom - boxRect.bottom,
      heights: [boxRect.height, gutRect.height],
      scroll: [box.scrollTop, gutter.scrollTop],
      // The row pitch has to be the text's own, or the column drifts by a
      // fraction of a pixel per line and is a whole line out by line 30.
      metrics: [boxStyle.lineHeight === style.lineHeight],
      sizes: [boxStyle.fontSize, style.fontSize],
      worst: Math.max(...rows.map((r) => Math.abs(r.delta))),
      rows,
    };
  };

  const gutterOk = (where, m) => {
    ok(`gutter (${where}) is clipped to the textarea, not the row`,
      !m.missing && Math.abs(m.overflow) <= 1,
      m.missing ? "no gutter" : `${m.overflow.toFixed(1)}px past the box, heights ${m.heights.map((h) => h.toFixed(0)).join(" vs ")}`);
    ok(`gutter (${where}) takes the textarea's own line-height (its numbers are smaller on purpose)`,
      !m.missing && m.metrics.every(Boolean), m.missing ? "no gutter" : JSON.stringify(m.sizes));
    ok(`gutter (${where}) scrolls in lock-step`,
      !m.missing && m.scroll[0] === m.scroll[1], `box ${m.scroll[0]}, gutter ${m.scroll[1]}`);
    ok(`gutter (${where}) number baselines sit on the text's within 1px`,
      !m.missing && m.worst <= 1,
      m.missing ? "no gutter" : m.rows.map((r) => `${r.n}:${r.delta.toFixed(2)}`).join(" "));
  };

  // --- the capture form. `#capture` is a hidden card until the section is
  // shown, and a textarea inside `display: none` measures zero.
  await page.evaluate(async (content) => {
    switchTab("notes");
    showNotesSection("capture", { focus: true });
    await new Promise((r) => setTimeout(r, 400));
    const box = document.getElementById("entry-content");
    box.value = content;
    box.dispatchEvent(new Event("input", { bubbles: true }));
    applyDocGutter();
    await new Promise((r) => setTimeout(r, 400));
  }, GUTTER_LINES);
  await page.waitForTimeout(500);
  await page.evaluate(async () => {
    const box = document.getElementById("entry-content");
    box.scrollTop = 120;
    box.dispatchEvent(new Event("scroll", { bubbles: true }));
    await new Promise((r) => requestAnimationFrame(r));
  });
  gutterOk("capture form", await page.evaluate(`(${gutterMeasure})("entry-content")`));

  // --- the note edit form, whose gutter is built by `mountGutterFor` into a
  // detached <li> and whose line-height (24px) differs from the capture
  // form's (23.2px). One static CSS value could not have been right for both,
  // which is the argument for copying each box's own metrics.
  const editBox = await page.evaluate(async (content) => {
    const r = await api("/entries", { method: "POST", body: JSON.stringify({ content, tags: ["gutter"] }) });
    const made = await r.json();
    showNotesSection("browse");
    await loadEntries();
    editingId = made.id;
    renderEntries();
    await new Promise((wait) => setTimeout(wait, 600));
    applyDocGutter();
    const box = document.querySelector(".gutter-wrap > textarea:not(#entry-content)");
    if (!box) return { missing: true };
    box.scrollTop = 90;
    box.dispatchEvent(new Event("scroll", { bubbles: true }));
    return { id: box.id };
  }, GUTTER_LINES);
  await page.waitForTimeout(500);
  gutterOk("note edit form",
    editBox.missing ? { missing: true } : await page.evaluate(`(${gutterMeasure})("${editBox.id}")`));

  await page.waitForTimeout(400);
  ok("no console errors", consoleErrors.length === 0, JSON.stringify(consoleErrors.slice(0, 4)));

  await browser.close();
  console.log(`\n${checks - failures}/${checks} checks passed`);
  process.exit(failures ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
