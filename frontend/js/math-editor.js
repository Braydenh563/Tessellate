// math-editor.js: the guided equation editor (DOCUMENTS_PLAN row 16; the
// owner, 2026-10-26: "an easier and guided way to write out mathematical
// equations and symbols like with word or desmos"; and 2026-10-31, INBOX 1473:
// "word equations ... edit the boxes where stuff goes ... I want latex as well").
//
// One lazy module (lazy-entries.js `LAZY_MODULES.mathEditor`, with
// math-editor-lazy.css and the field it is built on, math-field.js). It is the
// Calculator's Equation tab (INBOX 1527, the owner: "the equations and
// calculator should be integrated together"): reply-kit.js's dialog hosts it
// through `mathEditorMount`, and every surface is a thin caller of
// `openMathEditor({target})`, which opens that dialog on the Equation tab:
// the "/" menu's Equation row in Notes, Documents, a board's text and the Chat
// box, the document's Insert menu, and Alt+= (Word's key) in any of those and
// in the Ask box.
//
// What it writes is TeX between `$` (inline) or `$$` (display), the dialect
// the one renderer already draws (`docMathRender`, documents.js), so a note
// stays plain text and the editor adds no second format. Its anatomy is the
// icon picker's, from the recipe index: a `.tabs-line` of Inline and Display,
// the '?' and the equation field, a `.search-field`, the palette's groups
// under pinned heads; Copy and Insert are the dialog's action row (reply-kit.js).
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
  //: Out of the Tab order; the group's current tile is put back by `mathEditorPalette`/`mathEditorRoving`.
  button.tabIndex = -1;
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
    //: One Tab stop per group (INBOX 1530 g M5: 149 stops on this tab, a long walk to the Insert row).
    grid.firstChild.tabIndex = 0;
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

//: Ctrl+Enter inserts, from the field or the LaTeX box; Escape, taken before
//: the field sees it (MathLive's own Escape is its LaTeX-entry switch, left
//: alone while the field is in that mode), closes the panel.
function mathEditorKeys(paneOf, insert, escape) {
  return (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      event.stopPropagation();
      insert();
    } else if (event.key === "Escape" && paneOf().field.mode !== "latex") {
      event.preventDefault();
      event.stopPropagation();
      escape();
    }
  };
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

//: **Writes `tex` into `target`** (a text box or an editor surface): as an
//: equation between dollars at `start` (`{from, to, editing}`, the equation
//: being edited), or, with `plain`, as it is at the selection (what the
//: Calculator's Insert buttons call, reply-kit.js; a caret inside a drawn
//: equation is not replaced, that is what the Equation tab edits). Returns
//: whether anything was written.
function mathEditorWrite(target, tex, { display = false, start = null, plain = false } = {}) {
  const surface = target ? mathEditorSurface(target) : null;
  let text = plain ? String(tex || "") : mathEditorOutput(tex, display);
  if (!surface || !text.trim()) return false;
  const value = String(surface.value || "");
  const caret = surface.selectionStart ?? value.length;
  const at = start || { from: caret, to: surface.selectionEnd ?? caret, editing: false };
  if (display && !plain && surface.tagName !== "INPUT" && !at.editing) text = mathEditorBlockText(value, at.from, at.to, text);
  if (surface.kind || surface.setSelectionRange) {
    editorSplice(surface, at.from, at.to, text, { from: text.length, to: text.length });
  } else {
    surface.value = value.slice(0, at.from) + text + value.slice(at.to);
    surface.dispatchEvent?.(new Event("input", { bubbles: true }));
  }
  return true;
}

//: The line under the field's tabs: what to do, then the '?' and the button
//: that shows the TeX.
function mathEditorLede(help, toggle) {
  const row = document.createElement("div");
  row.className = "math-editor-lede-row";
  const lede = document.createElement("p");
  lede.className = "muted math-editor-lede";
  lede.textContent = "Click a box to fill it, or pick a structure; it is written as TeX.";
  const tools = document.createElement("span");
  tools.className = "math-editor-lede-tools";
  tools.append(help, toggle);
  row.append(lede, tools);
  return row;
}

//: **Every surface calls this** (Alt+=, the "/" rows, a document's Insert
//: menu, the palette): the editor is the Calculator's Equation tab now
//: (INBOX 1527), so it opens that dialog over `target`. Returns once it is up.
function openMathEditor({ target = null } = {}) {
  return ensureModule("replyKit").then(() => openCalculator("", "equation", { target }));
}

//: **Builds the editor into `host`**, the Equation tab's pane (reply-kit.js
//: `replyCalcEquation`), for `target` (an editor surface or a text box; none
//: and Insert becomes Copy). `done` closes the dialog; `note` is an element
//: for the value line, and `onTex(tex)` hears each change; `focus: false` builds it
//: without taking the focus (an arrow onto the tab). Returns
//: `{close, focus, copy, insert, ready, label}`, or null while the field's library is not loaded.
function mathEditorMount({ host, target = null, done = () => {}, note = null, onTex = () => {}, focus = true }) {
  if (!mathFieldConfigure()) return null;
  const surface = target ? mathEditorSurface(target) : null;
  const start = surface ? mathEditorStart(surface) : { from: 0, to: 0, tex: "", display: false, editing: false };
  let display = start.display;

  host.classList.add("math-editor");
  const { help, body: helpBody } = mathEditorHelp();
  const close = () => {
    helpBody.remove();
    done();
  };
  //: The calculator's action row calls these (reply-kit.js `replyCalcActions`); Ctrl+Enter is Insert with a box and Copy without one.
  const view = {
    copy: () => {
      const text = mathEditorOutput(pane.tex(), display);
      if (!text) return pane.focus();
      navigator.clipboard?.writeText(text).then(() => toast("Equation copied."), () => toast("Couldn't copy the equation.", "info"));
    },
    insert: () => {
      if (mathEditorWrite(target, pane.tex(), { display, start })) close();
      else pane.focus();
    },
  };
  const escape = () => (helpBody.classList.contains("hidden") ? done() : help.click());
  const pane = mathFieldPane({
    tex: start.tex,
    label: "Equation",
    onChange: () => onTex(pane.tex()),
    onKey: mathEditorKeys(() => pane, () => (surface ? view.insert() : view.copy()), escape),
  });
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
  //: **A group of tiles is one Tab stop and the arrows walk it** (INBOX 1530 g
  //: M5), as the keypad's keys are: the tile that last had focus is the group's
  //: stop (`focusin` moves it, so a click does too); Left and Right step, Up and
  //: Down go to the nearest tile in the row above or below (across the groups),
  //: Home and End to the group's first and last. Delegated on the list, so a
  //: search that redraws the groups needs nothing again.
  const roving = (list) => {
    list.addEventListener("focusin", (event) => {
      const tile = event.target.closest?.(".math-editor-tile");
      if (!tile) return;
      for (const other of tile.parentElement.children) other.tabIndex = other === tile ? 0 : -1;
    });
    list.addEventListener("keydown", (event) => {
      const tile = event.target.closest?.(".math-editor-tile");
      if (!tile || event.altKey || event.ctrlKey || event.metaKey) return;
      const group = [...tile.parentElement.children];
      const all = [...list.querySelectorAll(".math-editor-tile")];
      const at = group.indexOf(tile);
      let next = null;
      if (event.key === "ArrowRight") next = group[at + 1] || all[all.indexOf(tile) + 1];
      else if (event.key === "ArrowLeft") next = group[at - 1] || all[all.indexOf(tile) - 1];
      else if (event.key === "Home") next = group[0];
      else if (event.key === "End") next = group[group.length - 1];
      else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const down = event.key === "ArrowDown";
        const from = tile.getBoundingClientRect();
        const centre = from.left + from.width / 2;
        //: Rows are told apart by their top edge; the nearest row first, then the nearest column in it.
        const others = all.filter((t) => (down ? t.getBoundingClientRect().top > from.top + 2 : t.getBoundingClientRect().top < from.top - 2));
        const row = others.length ? (down ? Math.min : Math.max)(...others.map((t) => t.getBoundingClientRect().top)) : null;
        const inRow = others.filter((t) => Math.abs(t.getBoundingClientRect().top - row) < 2);
        next = inRow.sort((a, b) => Math.abs(a.getBoundingClientRect().left + a.offsetWidth / 2 - centre) - Math.abs(b.getBoundingClientRect().left + b.offsetWidth / 2 - centre))[0];
      } else return;
      event.preventDefault();
      next?.focus();
    });
  };
  roving(list);

  list.addEventListener("click", (event) => {
    const tile = event.target.closest(".math-editor-tile");
    if (tile) pane.insert(tile._item.tex);
  });
  //: **No key leaves the pane** (the icon picker's rule): an Enter or a
  //: letter here must not reach the canvas or the editor behind it.
  host.addEventListener("keydown", (event) => event.stopPropagation());

  //: Copy and Insert are the dialog's action row, pinned under the panes (reply-kit.js), so neither is a scroll away.
  host.replaceChildren(mode.tabs, mathEditorLede(help, pane.toggle), helpBody, pane.el, ...(note ? [note] : []), search, list);
  initHelpToggles(host);
  if (focus) pane.start();
  onTex(pane.tex());
  return { close, focus: () => pane.focus(), copy: view.copy, insert: view.insert, ready: () => Boolean(pane.tex().trim()), label: start.editing ? "Update" : "Insert" };
}
