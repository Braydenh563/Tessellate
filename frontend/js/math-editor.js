// math-editor.js: the guided equation editor (DOCUMENTS_PLAN row 16; the
// owner, 2026-10-26: "an easier and guided way to write out mathematical
// equations and symbols like with word or desmos").
//
// One lazy module (lazy-entries.js `LAZY_MODULES.mathEditor`, with
// math-editor-lazy.css), and every surface is a thin caller of
// `openMathEditor({target, anchor})`: the "/" menu's Equation row in Notes,
// Documents, a board's text and the Chat box, the document's Insert menu, and
// Alt+= (Word's key) in any of those and in the Ask box.
//
// What it writes is TeX between `$` (inline) or `$$` (display), the dialect
// the one renderer already draws (`docMathRender`, documents.js), so a note
// stays plain text and the editor adds no second format. Its anatomy is the
// icon picker's, from the recipe index: the popover shell lifted to <body>,
// the dialog head with its '?' and X, a `.seg` of Inline and Display, the
// TeX box over a live preview, a `.search-field`, the palette's groups under
// pinned heads, and the dialog foot (Cancel, Insert).
//
// **Guided, as Word's linear format and Desmos are**: typing `a/` makes a
// fraction with the caret in its denominator, `^` and `_` open a slot, an
// operator or a space leaves a filled script, `alpha`, `pi`, `sqrt` or `sin`
// followed by a space become the symbol, `>=`, `!=`, `->` and `+-` become one
// sign. Tab goes to the next empty slot. Backspace straight after a change
// undoes it, so nothing typed is lost to a guess.

// MATH-EDITOR-CORE-BEGIN

//: The palette. A template's empty `{}` or `[]` is a slot, which Tab walks
//: and the preview draws as a box. `sample` is what a structure's tile shows,
//: drawn by the renderer; a symbol's tile is its glyph.
const MATH_EDITOR_STRUCTURES = [
  ["fraction", "\\frac{}{}", "\\frac{a}{b}"],
  ["square root", "\\sqrt{}", "\\sqrt{x}"],
  ["nth root", "\\sqrt[]{}", "\\sqrt[n]{x}"],
  ["power", "^{}", "x^{n}"],
  ["subscript", "_{}", "x_{i}"],
  ["subscript and power", "_{}^{}", "x_{i}^{n}"],
  ["sum", "\\sum_{}^{}", "\\sum_{i}^{n}"],
  ["product", "\\prod_{}^{}", "\\prod_{i}^{n}"],
  ["integral", "\\int_{}^{}", "\\int_{a}^{b}"],
  ["limit", "\\lim_{{} \\to {}}", "\\lim_{x \\to a}"],
  ["derivative", "\\frac{d}{d{}}", "\\frac{d}{dx}"],
  ["partial derivative", "\\frac{\\partial {}}{\\partial {}}", "\\frac{\\partial f}{\\partial x}"],
  ["brackets", "\\left( {} \\right)", "\\left( x \\right)"],
  ["absolute value", "\\left| {} \\right|", "\\left| x \\right|"],
  ["binomial", "\\binom{}{}", "\\binom{n}{k}"],
  ["vector", "\\vec{}", "\\vec{v}"],
  ["hat", "\\hat{}", "\\hat{x}"],
  ["bar", "\\overline{}", "\\overline{x}"],
  ["matrix", "\\begin{pmatrix} {} & {} \\\\ {} & {} \\end{pmatrix}", "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}"],
  ["square matrix", "\\begin{bmatrix} {} & {} \\\\ {} & {} \\end{bmatrix}", "\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}"],
  ["determinant", "\\begin{vmatrix} {} & {} \\\\ {} & {} \\end{vmatrix}", "\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}"],
  ["cases", "\\begin{cases} {} & {} \\\\ {} & {} \\end{cases}", "\\begin{cases} a & x > 0 \\\\ b & x \\le 0 \\end{cases}"],
  ["text", "\\text{}", "\\text{abc}"],
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

//: Every group as `{key, label, items: [{name, tex, glyph, sample}]}`.
function mathEditorGroups() {
  const groups = [{
    key: "structures",
    label: "Structures",
    items: MATH_EDITOR_STRUCTURES.map(([name, tex, sample]) => ({ name, tex, sample, glyph: "" })),
  }];
  for (const [key, label, pairs] of MATH_EDITOR_SYMBOLS) {
    const items = pairs.split(" ").map((pair) => {
      const [name, glyph] = pair.split("=");
      return { name, tex: `\\${name}`, glyph, sample: "" };
    });
    groups.push({ key, label, items });
  }
  return groups;
}

//: Words that become a command when a space (or a bracket, or an operator)
//: follows them: every symbol's name, and a few spellings people type.
const MATH_EDITOR_ALIASES = { inf: "infty", infinity: "infty", deg: "degree" };

function mathEditorWordCommand(word) {
  if (MATH_EDITOR_ALIASES[word]) return MATH_EDITOR_ALIASES[word];
  const known = mathEditorWordCommand.names || (mathEditorWordCommand.names = new Set(
    MATH_EDITOR_SYMBOLS.flatMap(([, , pairs]) => pairs.split(" ").map((pair) => pair.split("=")[0]))
  ));
  return known.has(word) ? word : null;
}

//: Two characters that are one sign.
const MATH_EDITOR_PAIRS = {
  ">=": "\\ge ", "<=": "\\le ", "!=": "\\ne ", "->": "\\to ", "=>": "\\Rightarrow ", "+-": "\\pm ", "~=": "\\approx ",
};

//: The index of the brace or bracket that opens the one closing at `at`, or -1.
function mathEditorMatch(text, at, open, close) {
  let depth = 0;
  for (let i = at; i >= 0; i -= 1) {
    if (text[i] === close) depth += 1;
    else if (text[i] === open) {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}

//: Inside `\text{...}`, where words are words: no change is made there.
function mathEditorInText(before) {
  const at = Math.max(before.lastIndexOf("\\text{"), before.lastIndexOf("\\mathrm{"), before.lastIndexOf("\\operatorname{"));
  if (at < 0) return false;
  let depth = 0;
  for (let i = before.indexOf("{", at); i < before.length; i += 1) {
    if (before[i] === "{") depth += 1;
    else if (before[i] === "}") depth -= 1;
  }
  return depth > 0;
}

//: Where the term that ends at the end of `text` starts: Word's rule for
//: what a `/` puts over the line. Groups and scripts first (`x^{2}`,
//: `\frac{a}{b}`), then one base: a bracketed group, a command, or a run of
//: letters and digits.
function mathEditorTermStart(text) {
  let at = text.length;
  for (;;) {
    const c = text[at - 1];
    if (c === "}") {
      const open = mathEditorMatch(text, at - 1, "{", "}");
      if (open < 0) return at;
      at = open;
    } else if ((c === "^" || c === "_") && at < text.length) {
      at -= 1;
    } else {
      break;
    }
  }
  if (text[at - 1] === ")") {
    const open = mathEditorMatch(text, at - 1, "(", ")");
    return open < 0 ? at : open;
  }
  let start = at;
  while (start > 0 && /[A-Za-z0-9.]/.test(text[start - 1])) start -= 1;
  if (start > 0 && text[start - 1] === "\\" && /^[A-Za-z]/.test(text.slice(start, at))) start -= 1;
  return start;
}

function mathEditorPair(before, typed, after) {
  const sign = MATH_EDITOR_PAIRS[before.slice(-1) + typed];
  if (!sign || before.slice(-2, -1) === "\\") return null;
  const head = before.slice(0, -1) + sign;
  return { value: head + after, caret: head.length };
}

function mathEditorScript(before, typed, after) {
  if ((typed !== "^" && typed !== "_") || after.startsWith("{") || before.endsWith("\\")) return null;
  return { value: `${before}${typed}{}${after}`, caret: before.length + 2 };
}

//: An operator or a space typed at the end of a filled `^{...}` or `_{...}`
//: steps out of it first, as Word's does: `x^2+1` is x squared, plus one.
function mathEditorLeave(before, typed, after) {
  if (!" +-=<>,".includes(typed) || !after.startsWith("}")) return null;
  const open = mathEditorMatch(`${before}}`, before.length, "{", "}");
  if (open < 1 || open === before.length - 1 || !"^_".includes(before[open - 1])) return null;
  const head = `${before}}${typed === " " ? "" : typed}`;
  return { value: head + after.slice(1), caret: head.length };
}

function mathEditorFraction(before, typed, after) {
  if (typed !== "/" || before.endsWith("\\")) return null;
  const start = mathEditorTermStart(before);
  let top = before.slice(start);
  if (top.startsWith("(") && mathEditorMatch(top, top.length - 1, "(", ")") === 0) top = top.slice(1, -1);
  const head = `${before.slice(0, start)}\\frac{${top}}{`;
  const caret = top ? head.length : before.slice(0, start).length + 6;
  return { value: `${head}}${after}`, caret };
}

function mathEditorWord(before, typed, after) {
  if (/[A-Za-z]/.test(typed)) return null;
  const found = /(?:^|[^A-Za-z\\])([A-Za-z]{2,})$/.exec(before);
  const name = found && mathEditorWordCommand(found[1]);
  const head = found ? before.slice(0, before.length - found[1].length) : "";
  if (name) {
    const kept = `${head}\\${name}${typed === " " ? " " : ` ${typed}`}`;
    return { value: kept + after, caret: kept.length };
  }
  if (found && found[1] === "sqrt") {
    const kept = `${head}\\sqrt{`;
    const rest = typed === " " || typed === "(" ? "" : typed;
    return { value: `${kept}}${rest}${after}`, caret: kept.length };
  }
  return null;
}

//: **The guided typing, as one pure step**: `value` has just had one
//: character typed at `caret - 1`. Returns the changed `{value, caret}`, or
//: null when the typing stands as it is.
function mathEditorAuto(value, caret) {
  const text = String(value || "");
  if (caret < 1 || caret > text.length) return null;
  const typed = text[caret - 1];
  const before = text.slice(0, caret - 1);
  const after = text.slice(caret);
  if (mathEditorInText(before)) return null;
  return mathEditorPair(before, typed, after)
    || mathEditorLeave(before, typed, after)
    || mathEditorScript(before, typed, after)
    || mathEditorFraction(before, typed, after)
    || mathEditorWord(before, typed, after);
}

const MATH_EDITOR_SLOT = /\{\}|\[\]/g;

//: The caret position inside the next empty slot after `from`, or -1.
function mathEditorNextSlot(value, from) {
  MATH_EDITOR_SLOT.lastIndex = 0;
  for (let m = MATH_EDITOR_SLOT.exec(value); m; m = MATH_EDITOR_SLOT.exec(value)) {
    if (m.index >= from) return m.index + 1;
  }
  return -1;
}

//: Where Tab goes: the next empty slot, else out past the brace the caret
//: is inside (Desmos's right arrow out of a denominator), else -1.
function mathEditorTabStop(value, from) {
  const slot = mathEditorNextSlot(value, from);
  if (slot >= 0) return slot;
  const close = value.indexOf("}", from);
  return close >= 0 ? close + 1 : -1;
}

//: The caret position inside the last empty slot that ends before `from`, or -1.
function mathEditorPrevSlot(value, from) {
  let best = -1;
  MATH_EDITOR_SLOT.lastIndex = 0;
  for (let m = MATH_EDITOR_SLOT.exec(value); m; m = MATH_EDITOR_SLOT.exec(value)) {
    if (m.index + 1 < from) best = m.index + 1;
  }
  return best;
}

//: A palette pick at the selection: a selection becomes the first slot's
//: content (select `x`, pick the fraction, and `x` is over the line); the
//: caret goes to the first slot still empty, or after the insert. A command
//: ending in letters gets a space, so `\alpha` and the next `x` stay two.
function mathEditorInsert(value, start, end, tex) {
  const text = String(value || "");
  const chosen = text.slice(start, end);
  let piece = /[A-Za-z]$/.test(tex) ? `${tex} ` : tex;
  if (chosen) {
    MATH_EDITOR_SLOT.lastIndex = 0;
    const slot = MATH_EDITOR_SLOT.exec(piece);
    piece = slot ? `${piece.slice(0, slot.index + 1)}${chosen}${piece.slice(slot.index + 1)}` : `${chosen}${piece}`;
  }
  const next = text.slice(0, start) + piece + text.slice(end);
  const inside = mathEditorNextSlot(next, start);
  const caret = inside >= 0 && inside <= start + piece.length ? inside : start + piece.length;
  return { value: next, caret };
}

//: What the preview draws: an empty slot as a box, so a half-built fraction
//: shows where its parts go.
function mathEditorPreviewTex(tex) {
  return String(tex || "").replace(/\{\}/g, "{□}").replace(/\[\]/g, "[□]");
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
  button.title = `${item.name}: ${item.tex}`;
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
      const hay = `${item.name} ${group.label} ${item.tex}`.toLowerCase();
      return words.every((word) => hay.includes(word));
    });
    if (!items.length) continue;
    const head = document.createElement("div");
    head.className = "math-editor-group";
    head.textContent = group.label;
    const grid = document.createElement("div");
    grid.className = group.key === "structures" ? "math-editor-grid math-editor-grid-wide" : "math-editor-grid";
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

function mathEditorDrawPreview(preview, tex, display) {
  const body = String(tex || "").trim();
  if (!body) {
    const hint = document.createElement("span");
    hint.className = "muted";
    hint.textContent = "The equation shows here as you type.";
    preview.replaceChildren(hint);
    return;
  }
  if (typeof docMathRender !== "function") {
    preview.textContent = body;
    ensureModule("library").then(() => {
      if (preview.isConnected && typeof docMathRender === "function") mathEditorDrawPreview(preview, tex, display);
    });
    return;
  }
  try {
    preview.replaceChildren(docMathRender(mathEditorPreviewTex(body), display));
  } catch {
    preview.textContent = body;
  }
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
    "Type it plainly: a/b makes a fraction, ^ and _ open a power or a subscript, and a space or an operator steps out of one. Names such as alpha, pi, sqrt, sum or sin become the symbol after a space, and >=, !=, -> and +- become one sign. Tab goes to the next empty box, Backspace straight after a change undoes it. Pick from the palette to insert at the cursor; a selection goes into the first box. Inline sits in a sentence, Display on its own line. Ctrl+Enter inserts. What is written is TeX between dollar signs, so the note stays plain text; put the cursor in an equation and open this again to edit it.";
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

//: Tab and Shift+Tab walk the empty slots; with none left they move the
//: focus as Tab always does. Ctrl+Enter inserts.
function mathEditorKeys(input, view) {
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      view.insert();
      return;
    }
    if (event.key === "Backspace" && view.undoAuto()) {
      event.preventDefault();
      return;
    }
    if (event.key !== "Tab" || event.ctrlKey || event.altKey) return;
    const at = event.shiftKey
      ? mathEditorPrevSlot(input.value, input.selectionStart)
      : mathEditorTabStop(input.value, input.selectionEnd);
    if (at < 0) return;
    event.preventDefault();
    input.setSelectionRange(at, at);
  });
}

//: The guided typing on the box: one change per typed character, kept so a
//: Backspace straight after puts back what was typed.
function mathEditorGuide(input, onChange) {
  let last = null;
  input.addEventListener("input", (event) => {
    last = null;
    if (event.inputType === "insertText" && event.data && event.data.length === 1) {
      const was = { value: input.value, caret: input.selectionStart };
      const changed = mathEditorAuto(input.value, input.selectionStart);
      if (changed) {
        input.value = changed.value;
        input.setSelectionRange(changed.caret, changed.caret);
        last = { was, now: changed.value };
      }
    }
    onChange();
  });
  return () => {
    if (!last || input.value !== last.now) return false;
    input.value = last.was.value;
    input.setSelectionRange(last.was.caret, last.was.caret);
    last = null;
    onChange();
    return true;
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

//: **Opens the editor** for `target` (an editor surface or a text box),
//: hung from `anchor` when given. Returns `{close, panel}`.
function openMathEditor({ target = null, anchor = null } = {}) {
  closeMathEditor();
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

  const lede = document.createElement("p");
  lede.className = "muted math-editor-lede";
  lede.textContent = "Type it plainly or pick a symbol; it is written as TeX.";

  const input = document.createElement("textarea");
  input.className = "math-editor-input";
  input.rows = 2;
  input.spellcheck = false;
  input.autocomplete = "off";
  input.setAttribute("aria-label", "Equation, as TeX");
  input.placeholder = "e.g. x^2 + y^2 = r^2, or a/b";
  input.value = start.tex;

  const preview = document.createElement("div");
  preview.className = "math-editor-preview";
  preview.setAttribute("aria-live", "polite");
  preview.setAttribute("aria-label", "Preview");
  const redraw = () => mathEditorDrawPreview(preview, input.value, display);
  const mode = mathEditorModes(display, (on, refocus = true) => {
    display = on;
    mode.sync(on);
    redraw();
    if (refocus) input.focus({ preventScroll: true });
  });

  const list = document.createElement("div");
  list.className = "math-editor-list";
  const search = mathEditorSearch((q) => mathEditorPalette(list, q));
  mathEditorPalette(list, "");

  const view = {
    insert: () => {
      if (mathEditorWrite(surface, start, input.value, display)) close(false);
      else input.focus({ preventScroll: true });
    },
    undoAuto: () => false,
  };
  view.undoAuto = mathEditorGuide(input, redraw);
  mathEditorKeys(input, view);
  const { foot } = mathEditorFoot(() => close(), view.insert, start.editing ? "Update" : "Insert");

  list.addEventListener("click", (event) => {
    const tile = event.target.closest(".math-editor-tile");
    if (!tile) return;
    const at = mathEditorInsert(input.value, input.selectionStart, input.selectionEnd, tile._item.tex);
    input.value = at.value;
    input.focus({ preventScroll: true });
    input.setSelectionRange(at.caret, at.caret);
    redraw();
  });

  //: **No key leaves the panel** (the icon picker's rule): an Enter or a
  //: letter here must not reach the canvas or the editor behind it.
  panel.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key !== "Escape") return;
    event.preventDefault();
    if (!helpBody.classList.contains("hidden")) help.click();
    else close();
  });
  //: An outside press closes it only while nothing has been typed: a
  //: half-written equation is not thrown away by a stray click.
  const outside = (event) => {
    if (panel.contains(event.target) || helpBody.contains(event.target)) return;
    if (input.value.trim() && input.value !== start.tex) return;
    close(false);
  };
  document.addEventListener("pointerdown", outside, true);

  panel.append(head, helpBody, mode.tabs, lede, input, preview, search, list, foot);
  document.body.appendChild(panel);
  initHelpToggles(panel);
  mathEditorPlace(panel, anchor);
  redraw();
  input.focus({ preventScroll: true });
  input.setSelectionRange(input.value.length, input.value.length);
  //: For a moment after opening, focus that lands outside comes back: an
  //: editor behind can mount and take it a frame later (the icon picker
  //: measured 127ms on the note composer's first use).
  const openedAt = performance.now();
  const keepFocus = (event) => {
    if (!panel.isConnected || performance.now() - openedAt > 800) {
      document.removeEventListener("focusin", keepFocus, true);
      return;
    }
    if (!panel.contains(event.target) && !helpBody.contains(event.target)) input.focus({ preventScroll: true });
  };
  document.addEventListener("focusin", keepFocus, true);
  mathEditorState.open = { panel, close };
  return { close, panel };
}
