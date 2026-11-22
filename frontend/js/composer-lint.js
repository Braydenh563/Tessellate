// composer-lint.js: Harper underlines in the chat box and the Ask box (L-chat-227, VC1), preloaded
// with the quickNote bundle. The lint, the findings filter and the fix popover are the documents' own
// (documents-prose.js, fetched with the library bundle on the first check); this file adds the
// mirror that paints the underlines and the click that opens the popover. The mirror is a sibling
// laid over the field, pointer-events off and its text transparent, so only the line shows and
// every click, caret and selection stays the field's own. Debounced like a note box (600 ms), so a
// keystroke costs one remap and one repaint, never a lint.
(() => {
  const COMPOSER_LINT_BOXES = "#chat-input, #question";
  const COMPOSER_LINT_DEBOUNCE_MS = 600;
  //: Under three words there is nothing to check; a slash command or a code fence is not prose.
  const COMPOSER_LINT_MIN_WORDS = 3;

  //: The mirror's text as runs: plain text and one run per finding, in order. A finding whose
  //: words have moved or that overlaps the one before is dropped, never drawn on the wrong words.
  function composerLintSegments(text, findings) {
    const out = [];
    let at = 0;
    const ordered = findings.map((finding, index) => ({ finding, index })).sort((a, b) => a.finding.start - b.finding.start);
    for (const { finding, index } of ordered) {
      if (finding.start < at || text.slice(finding.start, finding.end) !== finding.text) continue;
      if (finding.start > at) out.push({ text: text.slice(at, finding.start), index: null });
      out.push({ text: finding.text, index });
      at = finding.end;
    }
    out.push({ text: text.slice(at) + (text.endsWith("\n") ? " " : ""), index: null });
    return out.filter((run) => run.text !== "");
  }

  //: The look of the field the mirror has to share, so a character sits on the same pixel.
  const COPIED = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "letterSpacing", "wordSpacing", "lineHeight", "textIndent", "textTransform", "tabSize", "textAlign", "direction", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth", "boxSizing", "overflowWrap", "wordBreak"];

  const wired = new WeakMap();

  function proseOnly(text) {
    const trimmed = text.trim();
    if (trimmed.startsWith("/") || trimmed.includes("```")) return false;
    //: The one word count (settings-wiring.js), so CJK text counts as the editor counts it.
    return wordCount(trimmed) >= COMPOSER_LINT_MIN_WORDS;
  }

  function wire(input) {
    if (wired.has(input)) return;
    const mirror = document.createElement("div");
    mirror.className = "composer-lint-mirror";
    mirror.setAttribute("aria-hidden", "true");
    const area = input.tagName === "TEXTAREA";
    const ms = mirror.style;
    ms.position = "absolute";
    ms.pointerEvents = "none";
    ms.overflow = "hidden";
    ms.color = "transparent";
    ms.background = "transparent";
    ms.whiteSpace = area ? "pre-wrap" : "pre";
    ms.display = "none";
    ms.zIndex = "1";
    input.after(mirror);
    const state = { mirror, findings: [], text: "", checked: null, timer: 0, asked: 0 };
    wired.set(input, state);

    //: Geometry and look, re-read on every paint: the box grows as the draft does.
    function place() {
      const style = getComputedStyle(input);
      for (const name of COPIED) ms[name] = style[name];
      ms.left = `${input.offsetLeft}px`;
      ms.top = `${input.offsetTop}px`;
      ms.width = `${input.offsetWidth}px`;
      ms.height = `${input.offsetHeight}px`;
      //: A one-line input centres its text; a mirror div would start at the top, so the line is as tall as the content box.
      if (!area) ms.lineHeight = `${input.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)}px`;
      mirror.scrollTop = input.scrollTop;
      mirror.scrollLeft = input.scrollLeft;
    }

    function paint() {
      const live = state.findings.filter((finding) => input.value.slice(finding.start, finding.end) === finding.text);
      if (!live.length) {
        if (ms.display !== "none") mirror.replaceChildren();
        ms.display = "none";
        return;
      }
      ms.display = "block";
      place();
      const runs = composerLintSegments(input.value, state.findings);
      mirror.replaceChildren(...runs.map((run) => {
        if (run.index === null) return document.createTextNode(run.text);
        const mark = document.createElement("span");
        mark.textContent = run.text;
        mark.style.textDecoration = "underline double";
        mark.style.textDecorationColor = "var(--warn)";
        mark.style.textDecorationSkipInk = "none";
        mark.style.textUnderlineOffset = "0.18em";
        return mark;
      }));
      mirror.scrollTop = input.scrollTop;
      mirror.scrollLeft = input.scrollLeft;
    }

    async function check() {
      const text = input.value;
      if (text === state.checked || !proseOnly(text)) return;
      if (prefsCache && prefsCache.grammar_check === false) return;
      //: Findings exist only once the bundle is in, so the click below needs no guard of its own.
      if (!(await ensureModule("library"))) return;
      if (!docGrammarEnabled()) return;
      const lints = await docGrammarAsk(text);
      if (lints === null) return;
      //: The draft moved on while the lint ran: ask again when it settles.
      if (input.value !== text) return schedule();
      state.checked = text;
      state.text = text;
      state.findings = docGrammarFindings(lints, text);
      paint();
    }

    function schedule() {
      clearTimeout(state.timer);
      state.timer = setTimeout(check, COMPOSER_LINT_DEBOUNCE_MS);
    }

    //: The popover's three moves on a plain field. execCommand keeps the field's own undo.
    const host = {
      text: () => input.value,
      replace: (option, finding) => {
        input.focus();
        input.setSelectionRange(finding.start, finding.end);
        if (!document.execCommand("insertText", false, option)) {
          input.setRangeText(option, finding.start, finding.end, "end");
          input.dispatchEvent(new Event("input", { bubbles: true }));
        }
      },
      refresh: paint,
    };
    const plugin = state;

    input.addEventListener("input", () => {
      if (state.findings.length) state.findings = docProseRemap(state.findings, state.text, input.value);
      state.text = input.value;
      paint();
      schedule();
    });
    input.addEventListener("scroll", () => {
      mirror.scrollTop = input.scrollTop;
      mirror.scrollLeft = input.scrollLeft;
    });
    //: The box grows on input (paint re-places it); a window resize is the only other change of width.
    window.addEventListener("resize", () => state.findings.length && place());
    input.addEventListener("click", (event) => {
      const caret = input.selectionStart;
      if (caret !== input.selectionEnd || !state.findings.length) return;
      const finding = state.findings.find((item) => caret >= item.start && caret < item.end && input.value.slice(item.start, item.end) === item.text);
      if (finding) noteGrammarMenu({ noteHost: host }, plugin, finding, event.clientX, event.clientY);
    });
    if (input.value) schedule();
  }

  //: No exports: the module opens itself on a box's focus (preloaded with the quickNote bundle, app.js).
  document.addEventListener("focusin", (event) => {
    if (event.target.matches?.(COMPOSER_LINT_BOXES)) wire(event.target);
  });
  if (document.activeElement?.matches?.(COMPOSER_LINT_BOXES)) wire(document.activeElement);
  if (typeof window.__composerLintTest === "object") window.__composerLintTest.segments = composerLintSegments;
})();
