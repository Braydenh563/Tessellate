// math-field.js: Word-style equation fields (INBOX 1473 a; the owner,
// 2026-10-31: "click within the rendered blocks and edit the boxes where stuff
// goes ... also I want latex as well").
//
// MathLive (frontend/vendor/mathlive, MIT) draws and edits the equation as a
// structure with dotted empty boxes to click into; this file is the app's side
// of it, one lazy bundle (lazy-entries.js `LAZY_MODULES.mathField`: the
// library, math-field-lazy.css, this file), fetched on the first equation edit
// and never at boot. Two surfaces use it:
//
// - `openMathInPlace`, called by a rendered `$...$` in Notes and Documents
//   (documents.js `DocMathWidget`): a field over the widget, Enter or a click
//   outside writes the TeX back to the exact source range in one transaction
//   (one undo), Escape leaves the text untouched.
// - `mathFieldPane`, the field with its LaTeX toggle, which the guided
//   editor's panel (math-editor.js) also holds.
//
// What is stored does not change: TeX between `$` or `$$`, one line. An empty
// box is `\placeholder{}` while editing and `{}` in the text, so a half-filled
// fraction survives a reload as a half-filled fraction.

// MATH-FIELD-CORE-BEGIN

//: The index of the `}` that closes the `{` at `open`, or -1. A `\{` is a
//: brace to draw, not one to match.
function mathFieldGroupEnd(text, open) {
  let depth = 0;
  for (let i = open; i < text.length; i += 1) {
    if (text[i] === "\\") i += 1;
    else if (text[i] === "{") depth += 1;
    else if (text[i] === "}") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}

//: A field's TeX with each `\placeholder{...}` replaced by what is in it: an
//: empty box is `{}` again, a filled one is its content. MathLive writes a
//: box that is a whole argument without braces (`\frac{67}\placeholder{}`), and
//: the braces are what make it an argument, so a bare one comes back braced.
function mathFieldUnplace(latex) {
  let text = String(latex || "");
  for (let guard = 0; guard < 400; guard += 1) {
    const at = text.search(/\\placeholder(?![A-Za-z])/);
    if (at < 0) break;
    const open = text.indexOf("{", at);
    const close = open < 0 ? -1 : mathFieldGroupEnd(text, open);
    if (close < 0) break;
    const inner = text.slice(open + 1, close);
    const wrapped = /\{\s*$/.test(text.slice(0, at)) && /^\s*\}/.test(text.slice(close + 1));
    text = text.slice(0, at) + (wrapped ? inner : `{${inner}}`) + text.slice(close + 1);
  }
  return text;
}

//: The TeX written into the note: boxes unwrapped, one line (the Live view can
//: draw only a one-line formula, documents.js), a bare `$` escaped.
function mathFieldStored(latex) {
  const flat = mathFieldUnplace(latex).trim().replace(/\s*\n\s*/g, " ");
  return flat.replace(/\\[\s\S]|\$/g, (piece) => (piece === "$" ? "\\$" : piece));
}

//: The TeX a field is given: each empty `{}` a box to click into.
function mathFieldBoxes(tex) {
  return String(tex || "").replace(/\{\s*\}/g, "{\\placeholder{}}");
}

//: The change that writes `tex` over the equation `span` (`{from, to, delim}`)
//: in `source`: `{from, to, insert}`, or null when the text there is no longer
//: that equation (an edit elsewhere moved it) or nothing changed. An emptied
//: equation is removed.
function mathFieldChange(source, span, tex) {
  const { from, to, delim } = span;
  const was = String(source).slice(from, to);
  if (was.length < delim.length * 2 + 1 || !was.startsWith(delim) || !was.endsWith(delim)) return null;
  const insert = tex ? `${delim}${tex}${delim}` : "";
  return insert === was ? null : { from, to, insert };
}

// MATH-FIELD-CORE-END

const mathFieldState = { open: null, ready: false };

function mathFieldTouch() {
  return !!window.matchMedia?.("(pointer: coarse)").matches;
}

//: **MathLive writes `style="..."` into the markup it draws** (a fraction's
//: height, a sqrt's rule), and the page's policy (`style-src 'self'`, no
//: `unsafe-inline`) refuses an inline style attribute, so the first render drew
//: every structure flat and logged a violation per atom (80 for one formula).
//: Loosening the policy for the whole app is the wrong repair, and Mermaid's
//: own frame is for a library that cannot be told apart from the page; here the
//: markup is a string the library builds, so the repair is to apply it the way
//: the policy does allow, through CSSOM. A string that carries `style=` has the
//: attribute renamed before it is parsed (so nothing is refused) and each
//: renamed element's text set as `el.style.cssText` straight after, in the same
//: call, so a caret measured right after a render sees the finished layout.
//: Only a string that has `style=` pays anything.
function mathFieldAllowStyles() {
  const own = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
  if (!own?.set || own.set.mathField) return;
  const attribute = /(<[a-zA-Z][^<>]*?)\sstyle=("[^"]*"|'[^']*'|[^\s>"']+)/g;
  const set = function setInnerHtml(value) {
    if (typeof value !== "string" || !value.includes("style=")) {
      own.set.call(this, value);
      return;
    }
    own.set.call(this, value.replace(attribute, "$1 data-ml-style=$2"));
    for (const el of (this.content || this).querySelectorAll("[data-ml-style]")) {
      el.style.cssText = el.getAttribute("data-ml-style").replace(/^["']|["']$/g, "");
      el.removeAttribute("data-ml-style");
    }
  };
  set.mathField = true;
  Object.defineProperty(Element.prototype, "innerHTML", { ...own, set });
}

//: Once per page, before the first field: the policy shim, the fonts from the
//: vendored folder (never a CDN), no keypress sounds (none are shipped).
function mathFieldConfigure() {
  if (mathFieldState.ready) return true;
  if (typeof MathfieldElement === "undefined") return false;
  mathFieldAllowStyles();
  MathfieldElement.fontsDirectory = "/vendor/mathlive/fonts";
  MathfieldElement.soundsDirectory = null;
  MathfieldElement.keypressVibration = false;
  mathFieldState.ready = true;
  return true;
}

//: One field. The virtual keyboard is offered on a touch screen only, and the
//: menu is off: its colour and font styles are not TeX the renderer draws.
function mathFieldCreate(label) {
  mathFieldConfigure();
  const field = new MathfieldElement();
  field.className = "math-field";
  field.setAttribute("aria-label", label);
  field.mathVirtualKeyboardPolicy = mathFieldTouch() ? "auto" : "manual";
  field.addEventListener("mount", () => {
    field.menuItems = [];
  });
  return field;
}

function mathFieldRead(field) {
  return mathFieldStored(field.getValue("latex"));
}

function mathFieldWrite(field, tex) {
  field.setValue(mathFieldBoxes(tex), { silenceNotifications: true });
}

//: The LaTeX box and the button that shows it.
function mathFieldLatexBox() {
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ghost small math-field-toggle";
  toggle.textContent = "LaTeX";
  toggle.title = "Show the equation as LaTeX to edit it directly";
  toggle.setAttribute("aria-pressed", "false");
  const box = document.createElement("textarea");
  box.className = "math-field-latex hidden";
  box.rows = 2;
  box.spellcheck = false;
  box.autocomplete = "off";
  box.setAttribute("aria-label", "Equation, as LaTeX");
  return { toggle, box };
}

//: The field with its LaTeX toggle, the two kept in step: a change in the field
//: rewrites the box, a change in the box redraws the field. `tex()` is the
//: stored TeX; `insert(template)` puts a template (with `#@` and `#?` boxes)
//: at the cursor, a selection going into `#@`.
function mathFieldPane({ tex = "", label = "Equation", onChange = () => {}, onKey = null } = {}) {
  const el = document.createElement("div");
  el.className = "math-field-pane";
  const field = mathFieldCreate(label);
  const { toggle, box } = mathFieldLatexBox();
  el.append(field, box);
  mathFieldWrite(field, tex);
  box.value = tex;
  field.addEventListener("input", () => {
    box.value = mathFieldRead(field);
    onChange();
  });
  box.addEventListener("input", () => {
    mathFieldWrite(field, box.value);
    onChange();
  });
  toggle.addEventListener("click", () => {
    const on = box.classList.toggle("hidden") === false;
    toggle.setAttribute("aria-pressed", String(on));
    (on ? box : field).focus({ preventScroll: true });
  });
  if (onKey) el.addEventListener("keydown", onKey, true);
  return {
    el,
    field,
    toggle,
    tex: () => mathFieldRead(field),
    set: (next) => {
      mathFieldWrite(field, next);
      box.value = next;
    },
    focus: () => field.focus({ preventScroll: true }),
    //: Focus for a field that has just opened, with the first empty box
    //: selected when there is one (so typing fills it, as clicking a fraction
    //: with nothing under it asks for), else the caret at the end.
    start: () => {
      field.focus({ preventScroll: true });
      if (!/\{\s*\}/.test(box.value)) return;
      field.position = 0;
      field.executeCommand("moveToNextPlaceholder");
    },
    //: A structure's first box takes the selection; with none it is a box
    //: like the rest (MathLive's `#@` would otherwise reach back and wrap the
    //: last thing typed, which Word's gallery never does).
    insert: (template) => {
      const text = field.selectionIsCollapsed ? template.replace(/#@/g, "#?") : template;
      field.insert(text, { format: "latex", selectionMode: "placeholder", focus: true, feedback: false });
    },
  };
}

//: Whether a press landed on MathLive's own surfaces, which it puts on <body>
//: (the virtual keyboard, its key variants and its menus): not "outside".
function mathFieldOwns(target) {
  return !!target?.closest?.(".ML__keyboard, .MLK__variant-panel, .MLK__plate, .MLK__backdrop, .ui-menu-container");
}

function closeMathInPlace(back = true) {
  mathFieldState.open?.close(back);
}

//: Where the field hangs: over the equation it edits, and on a touch screen at
//: the top of the window, out from under MathLive's keyboard.
function mathFieldPlace(pop, rect) {
  const margin = 8;
  const touch = mathFieldTouch();
  const width = touch ? window.innerWidth - margin * 2 : Math.min(window.innerWidth - margin * 2, Math.max(rect.width, 288));
  pop.style.width = `${width}px`;
  const left = Math.min(Math.max(margin, rect.left), window.innerWidth - margin - width);
  pop.style.left = `${left}px`;
  const top = touch ? margin : Math.min(Math.max(margin, rect.top - 6), window.innerHeight - pop.offsetHeight - margin);
  pop.style.top = `${Math.max(margin, top)}px`;
}

//: The foot: the LaTeX toggle on the left, Cancel and Done on the right.
function mathFieldFoot(toggle, cancel, done) {
  const foot = document.createElement("div");
  foot.className = "math-field-foot";
  const actions = document.createElement("div");
  actions.className = "row right";
  const ok = smallButton("Done", "Write the equation into the text (Enter)", done, false);
  ok.classList.add("primary");
  actions.append(smallButton("Cancel", "Leave the equation as it was (Escape)", cancel), ok);
  foot.append(toggle, actions);
  return foot;
}

//: **Edits the equation `{from, to}` of a note or document in place.** `view`
//: is the CodeMirror view, `host` the rendered widget it replaces, `delim` the
//: `$` or `$$` around it. Opens over the widget; Enter, Done or a click outside
//: writes the TeX back to that exact range in one transaction (one undo step),
//: Escape and Cancel leave the text byte for byte as it was.
function openMathInPlace({ view, host, from, to, delim, tex }) {
  closeMathInPlace(false);
  if (!mathFieldConfigure()) return null;
  const span = { from, to, delim };
  const pop = document.createElement("div");
  pop.className = "help-popover math-field-pop";
  pop.setAttribute("role", "group");
  pop.setAttribute("aria-label", "Edit equation");
  const rect = () => (host?.isConnected ? host.getBoundingClientRect() : view.coordsAtPos(from) || { left: 8, top: 8, width: 0 });
  let finished = false;
  const finish = (write, back = true) => {
    if (finished) return;
    finished = true;
    const next = pane.tex();
    document.removeEventListener("pointerdown", outside, true);
    window.removeEventListener("resize", place);
    window.removeEventListener("scroll", place, true);
    pop.remove();
    if (mathFieldState.open?.pop === pop) mathFieldState.open = null;
    if (write) {
      const change = mathFieldChange(view.state.doc.toString(), span, next);
      if (change) view.dispatch({ changes: change, userEvent: "input.math", scrollIntoView: false });
    }
    if (back) view.focus();
  };
  const pane = mathFieldPane({
    tex,
    onKey: (event) => mathFieldKeys(event, pane, finish),
  });
  const place = () => mathFieldPlace(pop, rect());
  const outside = (event) => {
    if (pop.contains(event.target) || mathFieldOwns(event.target)) return;
    finish(true, false);
  };
  pop.append(pane.el, mathFieldFoot(pane.toggle, () => finish(false), () => finish(true)));
  document.body.appendChild(pop);
  place();
  document.addEventListener("pointerdown", outside, true);
  window.addEventListener("resize", place);
  window.addEventListener("scroll", place, true);
  pane.start();
  mathFieldState.open = { pop, close: (back = true) => finish(false, back) };
  return mathFieldState.open;
}

//: Enter writes it, Escape drops it; both are taken before the field sees
//: them (MathLive's own Escape is its LaTeX-entry switch, left alone while the
//: field is in that mode so a half-typed `\frac` can be abandoned first).
function mathFieldKeys(event, pane, finish) {
  if (event.key === "Escape" && pane.field.mode !== "latex") {
    event.preventDefault();
    event.stopPropagation();
    finish(false);
  } else if (event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey && event.target !== pane.el.querySelector("textarea")) {
    event.preventDefault();
    event.stopPropagation();
    finish(true);
  }
}
