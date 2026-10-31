// math-editor.js: the guided equation editor (DOCUMENTS_PLAN row 16; the
// owner, 2026-10-26: "an easier and guided way to write out mathematical
// equations and symbols like with word or desmos"; and 2026-10-31, INBOX 1473:
// "word equations ... edit the boxes where stuff goes ... I want latex as well").
//
// One lazy module (lazy-entries.js `LAZY_MODULES.mathEditor`, with
// math-editor-lazy.css and the field it is built on, math-field.js), and every
// surface is a thin caller of `openMathEditor({target, anchor})`: the "/"
// menu's Equation row in Notes, Documents, a board's text and the Chat box, the
// document's Insert menu, and Alt+= (Word's key) in any of those and in the
// Ask box.
//
// What it writes is TeX between `$` (inline) or `$$` (display), the dialect
// the one renderer already draws (`docMathRender`, documents.js), so a note
// stays plain text and the editor adds no second format. Its anatomy is the
// icon picker's, from the recipe index: the popover shell lifted to <body>,
// the dialog head with its '?' and X, a `.tabs-line` of Inline and Display, the
// equation field, a `.search-field`, the palette's groups under pinned heads,
// and the dialog foot (Cancel, Insert).
//
// **The equation is a MathLive field, as Word's is** (math-field.js): a
// structure drawn as it will read with dotted boxes where things go, which
// are clicked or reached with Tab, `\frac` and the rest typed as LaTeX
// converting as they are typed, `/` making a fraction, `^` and `_` a script.
// The palette inserts a structure at the cursor (a selection goes into its
// first box), and the LaTeX button shows the same equation as raw TeX in a text
// box that stays in step with the field. It replaces the guided typing this
// file had for a plain text box: the field does all of that natively.

// MATH-EDITOR-CORE-BEGIN

//: The palette, as Word's equation ribbon groups it. A template's `#@` is the
//: box that takes the selection and `#?` any other box (MathLive's own
//: placeholders); `sample` is what its tile draws, by the renderer.
const MATH_EDITOR_TEMPLATES = [
  ["fraction", "Fraction", [
    ["fraction", "\\frac{#@}{#?}", "\\frac{a}{b}"],
    ["small fraction", "\\tfrac{#@}{#?}", "\\tfrac{a}{b}"],
    ["derivative", "\\frac{d#@}{d#?}", "\\frac{dy}{dx}"],
    ["partial derivative", "\\frac{\\partial #@}{\\partial #?}", "\\frac{\\partial f}{\\partial x}"],
    ["binomial", "\\binom{#@}{#?}", "\\binom{n}{k}"],
  ]],
  ["script", "Script", [
    ["superscript", "#@^{#?}", "x^{n}"],
    ["subscript", "#@_{#?}", "x_{i}"],
    ["subscript and superscript", "#@_{#?}^{#?}", "x_{i}^{n}"],
  ]],
  ["radical", "Radical", [
    ["square root", "\\sqrt{#@}", "\\sqrt{x}"],
    ["nth root", "\\sqrt[#?]{#@}", "\\sqrt[n]{x}"],
  ]],
  ["integral", "Integral", [
    ["integral", "\\int_{#?}^{#?}#@", "\\int_{a}^{b}f"],
    ["double integral", "\\iint_{#?}#@", "\\iint_{D}f"],
    ["triple integral", "\\iiint_{#?}#@", "\\iiint_{V}f"],
    ["contour integral", "\\oint_{#?}#@", "\\oint_{C}f"],
  ]],
  ["operator-large", "Large operator", [
    ["sum", "\\sum_{#?}^{#?}#@", "\\sum_{i}^{n}a"],
    ["product", "\\prod_{#?}^{#?}#@", "\\prod_{i}^{n}a"],
    ["coproduct", "\\coprod_{#?}^{#?}#@", "\\coprod_{i}^{n}a"],
    ["union", "\\bigcup_{#?}^{#?}#@", "\\bigcup_{i}^{n}A"],
    ["intersection", "\\bigcap_{#?}^{#?}#@", "\\bigcap_{i}^{n}A"],
  ]],
  ["bracket", "Bracket", [
    ["parentheses", "\\left(#@\\right)", "\\left(x\\right)"],
    ["square brackets", "\\left[#@\\right]", "\\left[x\\right]"],
    ["braces", "\\left\\{#@\\right\\}", "\\left\\{x\\right\\}"],
    ["absolute value", "\\left|#@\\right|", "\\left|x\\right|"],
    ["floor", "\\left\\lfloor #@\\right\\rfloor", "\\left\\lfloor x\\right\\rfloor"],
    ["ceiling", "\\left\\lceil #@\\right\\rceil", "\\left\\lceil x\\right\\rceil"],
    ["angle brackets", "\\left\\langle #@\\right\\rangle", "\\left\\langle x\\right\\rangle"],
  ]],
  ["function", "Function", [
    ["sine", "\\sin\\left(#@\\right)", "\\sin\\left(x\\right)"],
    ["cosine", "\\cos\\left(#@\\right)", "\\cos\\left(x\\right)"],
    ["tangent", "\\tan\\left(#@\\right)", "\\tan\\left(x\\right)"],
    ["logarithm", "\\log\\left(#@\\right)", "\\log\\left(x\\right)"],
    ["logarithm with base", "\\log_{#?}\\left(#@\\right)", "\\log_{b}\\left(x\\right)"],
    ["natural logarithm", "\\ln\\left(#@\\right)", "\\ln\\left(x\\right)"],
    ["exponential", "e^{#@}", "e^{x}"],
  ]],
  ["accent", "Accent", [
    ["hat", "\\hat{#@}", "\\hat{x}"],
    ["bar", "\\overline{#@}", "\\overline{x}"],
    ["tilde", "\\tilde{#@}", "\\tilde{x}"],
    ["dot", "\\dot{#@}", "\\dot{x}"],
    ["double dot", "\\ddot{#@}", "\\ddot{x}"],
    ["vector", "\\vec{#@}", "\\vec{v}"],
  ]],
  ["limit", "Limit and log", [
    ["limit", "\\lim_{#? \\to #?}#@", "\\lim_{x \\to a}f"],
    ["limit to infinity", "\\lim_{#? \\to \\infty}#@", "\\lim_{n \\to \\infty}a"],
    ["maximum", "\\max_{#?}#@", "\\max_{x}f"],
    ["minimum", "\\min_{#?}#@", "\\min_{x}f"],
    ["supremum", "\\sup_{#?}#@", "\\sup_{x}f"],
    ["infimum", "\\inf_{#?}#@", "\\inf_{x}f"],
  ]],
  ["operator", "Operator", [
    ["right arrow", "#@ \\to #?", "a \\to b"],
    ["arrow both ways", "#@ \\leftrightarrow #?", "a \\leftrightarrow b"],
    ["implies", "#@ \\Rightarrow #?", "a \\Rightarrow b"],
    ["text", "\\text{#@}", "\\text{abc}"],
  ]],
  ["matrix", "Matrix", [
    ["2 by 2 matrix", "\\begin{pmatrix}#@&#?\\\\#?&#?\\end{pmatrix}", "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}"],
    ["3 by 3 matrix", "\\begin{pmatrix}#@&#?&#?\\\\#?&#?&#?\\\\#?&#?&#?\\end{pmatrix}", "\\begin{pmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{pmatrix}"],
    ["square bracket matrix", "\\begin{bmatrix}#@&#?\\\\#?&#?\\end{bmatrix}", "\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}"],
    ["determinant", "\\begin{vmatrix}#@&#?\\\\#?&#?\\end{vmatrix}", "\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}"],
    ["cases", "\\begin{cases}#@&#?\\\\#?&#?\\end{cases}", "\\begin{cases} a & x > 0 \\\\ b & x \\le 0 \\end{cases}"],
  ]],
];

//: Symbol groups as `name=glyph` pairs: the TeX is `\name`, which the
//: renderer draws as the glyph (tests/test_math_editor.py checks every one).
const MATH_EDITOR_SYMBOLS = [
  ["greek", "Greek", "alpha=α beta=β gamma=γ delta=δ epsilon=ε zeta=ζ eta=η theta=θ iota=ι kappa=κ lambda=λ mu=μ nu=ν xi=ξ pi=π rho=ρ sigma=σ tau=τ upsilon=υ phi=φ chi=χ psi=ψ omega=ω Gamma=Γ Delta=Δ Theta=Θ Lambda=Λ Xi=Ξ Pi=Π Sigma=Σ Phi=Φ Psi=Ψ Omega=Ω"],
  ["operators", "Operators", "times=× div=÷ cdot=⋅ pm=± mp=∓ circ=∘ oplus=⊕ otimes=⊗ star=⋆ infty=∞ ldots=… cdots=⋯ degree=°"],
  ["relations", "Relations", "ne=≠ le=≤ ge=≥ approx=≈ equiv=≡ sim=∼ propto=∝ perp=⊥ parallel=∥ angle=∠"],
  ["arrows", "Arrows", "to=→ leftarrow=← leftrightarrow=↔ Rightarrow=⇒ mapsto=↦"],
  ["sets", "Sets and logic", "in=∈ notin=∉ subset=⊂ subseteq=⊆ supset=⊃ cup=∪ cap=∩ emptyset=∅ forall=∀ exists=∃ neg=¬ land=∧ lor=∨"],
  ["calculus", "Calculus", "sum=∑ prod=∏ int=∫ iint=∬ oint=∮ partial=∂ nabla=∇ lim=lim sin=sin cos=cos tan=tan log=log ln=ln exp=exp"],
];

//: Every group as `{key, label, items: [{name, tex, glyph, sample}]}`: the
//: structures first, then the symbols.
function mathEditorGroups() {
  const groups = MATH_EDITOR_TEMPLATES.map(([key, label, items]) => ({
    key,
    label,
    structures: true,
    items: items.map(([name, tex, sample]) => ({ name, tex, sample, glyph: "" })),
  }));
  for (const [key, label, pairs] of MATH_EDITOR_SYMBOLS) {
    const items = pairs.split(" ").map((pair) => {
      const [name, glyph] = pair.split("=");
      return { name, tex: `\\${name}`, glyph, sample: "" };
    });
    groups.push({ key, label, structures: false, items });
  }
  return groups;
}

//: The markdown written into the note, always on one line: no spaces inside
//: the dollars (`docMathLooksLikeMath` reads " x " as prose), and display as
//: `$$...$$` on one line because the Live view can only draw a one-line
//: formula (a replace decoration may not span a line break, documents.js);
//: a display one goes in a paragraph of its own (`mathEditorBlockText`).
function mathEditorOutput(tex, display) {
  const body = String(tex || "").trim().replace(/\s*\n\s*/g, " ");
  if (!body) return "";
  return display ? `$$${body}$$` : `$${body}$`;
}

//: The equation the selection is in, to edit it: a selection that is one
//: (`$x$`, `$$...$$`), or a caret inside one. `{from, to, tex, display}` or null.
function mathEditorSpan(value, start, end) {
  const text = String(value || "");
  const picked = text.slice(start, end);
  const whole = /^\$\$([\s\S]*?)\$\$$/.exec(picked) || /^\$([^$\n]+)\$$/.exec(picked);
  if (whole) return { from: start, to: end, tex: whole[1].trim(), display: picked.startsWith("$$") };
  const open = text.lastIndexOf("$$", start);
  const close = text.indexOf("$$", Math.max(end, open + 2));
  const before = text.slice(0, open).split("$$").length - 1;
  if (open >= 0 && open + 2 <= start && close >= end && before % 2 === 0 && close > open) {
    return { from: open, to: close + 2, tex: text.slice(open + 2, close).trim(), display: true };
  }
  const lineStart = text.lastIndexOf("\n", start - 1) + 1;
  const lineEnd = text.indexOf("\n", end) < 0 ? text.length : text.indexOf("\n", end);
  const line = text.slice(lineStart, lineEnd);
  const inline = /(^|[^$\\])\$([^\s$](?:[^$\n]*[^\s$])?)\$(?!\$)/g;
  for (let m = inline.exec(line); m; m = inline.exec(line)) {
    const from = lineStart + m.index + m[1].length;
    const to = from + m[2].length + 2;
    //: Strictly inside: a caret just before or after the dollars is beside
    //: the equation, where a new one goes.
    if (from < start && to > end) return { from, to, tex: m[2], display: false };
  }
  return null;
}
// MATH-EDITOR-CORE-END

const mathEditorState = { open: null };

function closeMathEditor() {
  mathEditorState.open?.close();
}

//: The surface the editor writes into: an editor adapter as it is, an
//: element through `editorSurfaceFor`, or the element itself (the Ask box).
function mathEditorSurface(target) {
  if (!target) return null;
  if (target.kind) return target;
  const surface = editorSurfaceFor(target);
  return surface || target;
}

//: A tile's face: a structure drawn by the renderer when it is loaded (the
//: library bundle is preloaded three seconds after boot), else its glyph.
function mathEditorTileFace(item) {
  if (item.sample && typeof docMathRender === "function") return docMathRender(item.sample, false);
  const face = document.createElement("span");
  face.className = "math-editor-glyph";
  face.textContent = item.glyph || item.sample;
  face.setAttribute("aria-hidden", "true");
  return face;
}

function mathEditorTile(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost math-editor-tile";
  button.title = item.name;
  button.setAttribute("aria-label", item.name);
  button._item = item;
  button.appendChild(mathEditorTileFace(item));
  return button;
}

//: The palette, filtered by the words typed: every word must be in the
//: name, the group's name or the TeX.
function mathEditorPalette(list, query) {
  const words = String(query || "").trim().toLowerCase().split(/\s+/).filter(Boolean);
  const parts = [];
  for (const group of mathEditorGroups()) {
    const items = group.items.filter((item) => {
      const hay = `${item.name} ${group.label} ${group.structures ? "" : item.tex}`.toLowerCase();
      return words.every((word) => hay.includes(word));
    });
    if (!items.length) continue;
    const head = document.createElement("div");
    head.className = "math-editor-group";
    head.textContent = group.label;
    const grid = document.createElement("div");
    grid.className = group.structures ? "math-editor-grid math-editor-grid-wide" : "math-editor-grid";
    grid.setAttribute("role", "group");
    grid.setAttribute("aria-label", group.label);
    grid.append(...items.map(mathEditorTile));
    parts.push(head, grid);
  }
  if (!parts.length) {
    const none = document.createElement("p");
    none.className = "muted math-editor-empty";
    none.textContent = "No symbol by that name. Try a shorter word.";
    parts.push(none);
  }
  list.replaceChildren(...parts);
}

function mathEditorHelp() {
  const help = document.createElement("button");
  help.type = "button";
  help.className = "icon-only ghost small dialog-head-btn";
  help.setAttribute("data-help-for", "math-editor-help");
  help.setAttribute("aria-controls", "math-editor-help");
  help.setAttribute("aria-expanded", "false");
  help.title = "About the equation editor";
  help.setAttribute("aria-label", "About the equation editor");
  const icon = document.createElement("i");
  icon.className = "ph ph-question";
  icon.setAttribute("aria-hidden", "true");
  help.appendChild(icon);
  const body = document.createElement("div");
  body.className = "help-body hidden";
  body.id = "math-editor-help";
  body.setAttribute("role", "dialog");
  body.setAttribute("aria-label", "About the equation editor");
  const text = document.createElement("p");
  text.textContent =
    "Click a dotted box to fill it, Tab goes to the next box and the arrows move through the equation. Type it as you would write it: / makes a fraction, ^ and _ open a power or a subscript, and LaTeX such as \\frac or \\alpha turns into the symbol as you type it. Pick a structure or a symbol from the palette to insert it at the cursor; a selection goes into the first box. The LaTeX button shows the same equation as raw TeX to edit directly. Inline sits in a sentence, Display on its own line. Ctrl+Enter inserts. What is written is TeX between dollar signs, so the note stays plain text; click a drawn equation in a note, or put the cursor in one and open this again, to edit it.";
  body.appendChild(text);
  return { help, body };
}

//: **Inline or Display is a tab strip under the head, never a pill** (the
//: recipe's "a popup chooses a kind" row, INBOX 715): one Tab stop, the
//: arrows and Home and End walk it.
function mathEditorModes(display, onChange) {
  const tabs = document.createElement("div");
  tabs.className = "tabs-line popup-kinds math-editor-mode";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Inline or display");
  const buttons = [["inline", "Inline", "In the sentence"], ["display", "Display", "On its own line, centred"]].map(([value, label, title]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.dataset.value = value;
    b.textContent = label;
    b.title = title;
    b.addEventListener("click", () => onChange(value === "display"));
    return b;
  });
  const sync = (on) => {
    for (const b of buttons) {
      const chosen = (b.dataset.value === "display") === on;
      b.setAttribute("aria-selected", String(chosen));
      b.tabIndex = chosen ? 0 : -1;
    }
  };
  tabs.addEventListener("keydown", (event) => {
    const to = { ArrowRight: 1, ArrowLeft: 0, Home: 0, End: 1 }[event.key];
    if (to === undefined) return;
    event.preventDefault();
    onChange(to === 1, false);
    buttons[to].focus();
  });
  tabs.append(...buttons);
  sync(display);
  return { tabs, sync };
}

function mathEditorSearch(onInput) {
  const field = document.createElement("div");
  field.className = "search-field math-editor-search";
  const lens = document.createElement("i");
  lens.className = "ph ph-magnifying-glass search-field-icon";
  lens.setAttribute("aria-hidden", "true");
  const input = document.createElement("input");
  input.type = "search";
  input.className = "search-field-input";
  input.autocomplete = "off";
  input.placeholder = "Search symbols";
  input.setAttribute("aria-label", "Search symbols");
  input.addEventListener("input", () => onInput(input.value));
  field.append(lens, input);
  return field;
}

//: Ctrl+Enter inserts, from the field or the LaTeX box.
function mathEditorKeys(insert) {
  return (event) => {
    if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
    event.preventDefault();
    event.stopPropagation();
    insert();
  };
}

function mathEditorFoot(onCancel, onInsert, label) {
  const foot = document.createElement("div");
  foot.className = "row right space-dialog-actions math-editor-foot";
  const cancel = smallButton("Cancel", "Close without inserting", onCancel);
  const insert = smallButton(label, "Write the equation into the text (Ctrl+Enter)", onInsert, false);
  insert.classList.add("primary");
  foot.append(cancel, insert);
  return { foot, insert };
}

//: Where the panel hangs: from the button that asked, else the middle.
function mathEditorPlace(panel, anchor) {
  const rect = anchor?.getBoundingClientRect?.();
  if (rect && (rect.width || rect.height)) placeHelpPopover(panel, anchor);
  else panel.classList.add("math-editor-centred");
}

//: What the editor opens on: the equation the selection is in, or the
//: selection as TeX, or nothing.
function mathEditorStart(surface) {
  const value = String(surface?.value || "");
  const start = surface?.selectionStart ?? value.length;
  const end = surface?.selectionEnd ?? start;
  const span = mathEditorSpan(value, start, end);
  if (span) return { ...span, editing: true };
  const picked = value.slice(start, end);
  return { from: start, to: end, tex: picked, display: picked.includes("\n"), editing: false };
}

//: The text written for a new display equation in a multi-line box: on its
//: own paragraph, as the "/" menu's blocks are.
function mathEditorBlockText(value, from, to, text) {
  const prior = value.slice(0, from);
  const next = value.slice(to);
  const lead = !prior.length || prior.endsWith("\n\n") ? "" : prior.endsWith("\n") ? "\n" : "\n\n";
  const trail = next.startsWith("\n\n") || !next.length ? "" : next.startsWith("\n") ? "\n" : "\n\n";
  return lead + text + trail;
}

function mathEditorWrite(surface, start, tex, display) {
  const oneLine = surface?.tagName === "INPUT";
  let text = mathEditorOutput(tex, display);
  if (!text || !surface) return false;
  const value = String(surface.value || "");
  if (display && !oneLine && !start.editing) text = mathEditorBlockText(value, start.from, start.to, text);
  if (surface.kind || surface.setSelectionRange) {
    editorSplice(surface, start.from, start.to, text, { from: text.length, to: text.length });
  } else {
    surface.value = value.slice(0, start.from) + text + value.slice(start.to);
    surface.dispatchEvent?.(new Event("input", { bubbles: true }));
  }
  return true;
}

//: The line under the head: what to do, and the button that shows the TeX.
function mathEditorLede(toggle) {
  const row = document.createElement("div");
  row.className = "math-editor-lede-row";
  const lede = document.createElement("p");
  lede.className = "muted math-editor-lede";
  lede.textContent = "Click a box to fill it, or pick a structure; it is written as TeX.";
  row.append(lede, toggle);
  return row;
}

//: **Opens the editor** for `target` (an editor surface or a text box),
//: hung from `anchor` when given. Returns `{close, panel}`.
function openMathEditor({ target = null, anchor = null } = {}) {
  closeMathEditor();
  if (!mathFieldConfigure()) return null;
  const surface = mathEditorSurface(target || document.activeElement);
  const start = mathEditorStart(surface);
  let display = start.display;
  const returnFocus = document.activeElement;

  const panel = document.createElement("div");
  panel.className = "help-popover math-editor";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Equation");
  const { help, body: helpBody } = mathEditorHelp();
  const close = (back = true) => {
    if (!panel.isConnected) return;
    document.removeEventListener("pointerdown", outside, true);
    panel.remove();
    helpBody.remove();
    if (mathEditorState.open?.panel === panel) mathEditorState.open = null;
    if (back) (returnFocus?.isConnected ? returnFocus : surface)?.focus?.({ preventScroll: true });
  };
  const head = dialogHead(start.editing ? "Edit equation" : "Equation", () => close());
  head.querySelector(".dialog-head-title")?.after(help);

  const view = {
    insert: () => {
      if (mathEditorWrite(surface, start, pane.tex(), display)) close(false);
      else pane.focus();
    },
  };
  const pane = mathFieldPane({ tex: start.tex, label: "Equation", onKey: mathEditorKeys(() => view.insert()) });
  pane.field.setAttribute("aria-describedby", "math-editor-help");
  const mode = mathEditorModes(display, (on, refocus = true) => {
    display = on;
    mode.sync(on);
    if (refocus) pane.focus();
  });

  const list = document.createElement("div");
  list.className = "math-editor-list";
  const search = mathEditorSearch((q) => mathEditorPalette(list, q));
  mathEditorPalette(list, "");
  const { foot } = mathEditorFoot(() => close(), view.insert, start.editing ? "Update" : "Insert");

  list.addEventListener("click", (event) => {
    const tile = event.target.closest(".math-editor-tile");
    if (tile) pane.insert(tile._item.tex);
  });

  //: **No key leaves the panel** (the icon picker's rule): an Enter or a
  //: letter here must not reach the canvas or the editor behind it.
  panel.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key !== "Escape" || pane.field.mode === "latex") return;
    event.preventDefault();
    if (!helpBody.classList.contains("hidden")) help.click();
    else close();
  });
  //: An outside press closes it only while nothing has been typed: a
  //: half-written equation is not thrown away by a stray click.
  const outside = (event) => {
    if (panel.contains(event.target) || helpBody.contains(event.target) || mathFieldOwns(event.target)) return;
    if (pane.tex() && pane.tex() !== start.tex) return;
    close(false);
  };
  document.addEventListener("pointerdown", outside, true);

  panel.append(head, helpBody, mode.tabs, mathEditorLede(pane.toggle), pane.el, search, list, foot);
  document.body.appendChild(panel);
  initHelpToggles(panel);
  mathEditorPlace(panel, anchor);
  pane.focus();
  //: For a moment after opening, focus that lands outside comes back: an
  //: editor behind can mount and take it a frame later (the icon picker
  //: measured 127ms on the note composer's first use).
  const openedAt = performance.now();
  const keepFocus = (event) => {
    if (!panel.isConnected || performance.now() - openedAt > 800) {
      document.removeEventListener("focusin", keepFocus, true);
      return;
    }
    if (!panel.contains(event.target) && !helpBody.contains(event.target)) pane.focus();
  };
  document.addEventListener("focusin", keepFocus, true);
  mathEditorState.open = { panel, close };
  return { close, panel };
}
