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
(() => {
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

  //: **Each empty `{}` is a box to click into**, whether the TeX is being set or
  //: has just been edited (INBOX 1538): MathLive writes a slot typed in and then
  //: deleted as a bare `{}`, which draws as a caret and no box, so the pane runs
  //: this after every edit as well. One already a box (`\placeholder{}`) and a
  //: brace to draw (`\{`) are left alone.
  function mathFieldBoxes(tex, bases = false) {
    const boxed = String(tex || "").replace(/(?<!\\placeholder)(?<!\\)\{\s*\}/g, "{\\placeholder{}}");
    //: With `bases`, a power or subscript whose base was deleted gets its box back too (`^{2}` alone is a caret and a floating 2).
    return bases ? boxed.replace(/(^|\{)(?=[\^_])/g, "$1\\placeholder{}") : boxed;
  }

  //: **A box that was typed into comes back when what was typed is deleted** (INBOX 1584 d). MathLive drops a box the
  //: moment a character replaces it, and `mathFieldBoxes` only knows an empty `{}`, so a matrix cell, the body of an
  //: integral, a limit beside other text (`\lim_{x \to a}`), a function's brackets and a root's index (which MathLive
  //: leaves out of the TeX when it is empty) were nothing at all once emptied. The pane remembers each box that was
  //: filled: `slots` are `[from, to)` offsets in the TeX of what now stands where a box was, moved by every later edit,
  //: and a slot a deletion empties is a `\placeholder{}` again. A slot an edit covers only in part is let go (the person
  //: is editing around it), and so is one inside a structure that was deleted whole. `collapsed` is whether the
  //: deletion was a single key press: only then is a root's index or a `\text{}` that vanished with its last character
  //: put back with its brackets. Returns the TeX, the slots, and `at`, the offset of the box put back (or -1).
  function mathFieldSlots(prev, next, slots, { collapsed = true, restore = true } = {}) {
    const MATH_FIELD_BOX = "\\placeholder{}";
    const was = String(prev);
    const now = String(next);
    if (was === now) return { tex: now, slots, at: -1 };
    const top = Math.min(was.length, now.length);
    let p = 0;
    while (p < top && was[p] === now[p]) p += 1;
    let s = 0;
    while (s < top - p && was[was.length - 1 - s] === now[now.length - 1 - s]) s += 1;
    const q = was.length - s;
    const m = now.length - s - p;
    const delta = m - (q - p);
    const kept = [];
    let tex = now;
    let at = -1;
    let put = { pos: -1, len: 0 };
    const putBack = (pos, text, box) => {
      if (at >= 0 || !restore) return;
      tex = now.slice(0, pos) + text + now.slice(pos);
      at = pos + box;
      put = { pos, len: text.length };
    };
    for (const slot of slots) {
      const [a, b, open = "", close = ""] = slot;
      if (q < a || (q === a && p < q)) kept.push([a + delta, b + delta, open, close]);
      //: A script's base whose script this edit removed is plain text now, not a box's stand-in, so deleting it later
      //: leaves nothing (INBOX 1623, the owner: "the box shouldnt appear now because it is only a regular number").
      else if (p === b && q > p && /[_^]/.test(was[b]) && !/[_^]/.test(now[b] || "")) continue;
      else if (p > b || (p === b && q > p)) kept.push(slot);
      else if (p >= a && q <= b) {
        if (b + delta > a) kept.push([a, b + delta, open, close]);
        else putBack(a, open + MATH_FIELD_BOX + close, open.length);
      } else if (p <= a && q >= b && collapsed && m === 0) {
        //: The diff's edges can run into the text beside what was removed (`\log` and `\left` both start `\l`), so the wrapper is read from the slot outwards (with its command, then without: `\log_{x}` goes whole, `\sqrt[x]` leaves its root) and checked against the new TeX.
        const close = was[b];
        for (const shape of [/(\\[a-zA-Z]+)?[_^]?[[{]$/, /[_^]?[[{]$/]) {
          const open = shape.exec(was.slice(0, a));
          const from = open ? a - open[0].length : -1;
          if (open && (close === "]" || close === "}") && was.slice(0, from) + was.slice(b + 1) === now) {
            putBack(from, open[0] + MATH_FIELD_BOX + close, open[0].length);
            break;
          }
        }
      }
    }
    //: A box that a plain character replaced is a new slot. A structure typed in (a `/` makes a fraction) or pasted in is not: it has boxes of its own. Typing into `\text{}` leaves the letters bare, so that slot remembers its `\text{` and `}`.
    const gone = was.slice(p, q);
    if (m > 0 && (/^\\placeholder(\[[^\]]*\])?\{\}$/.test(gone) || /^\\text\{\\placeholder(\[[^\]]*\])?\{\}\}$/.test(gone))) {
      const text = gone.startsWith("\\text");
      const wrapped = !text && m > 2 && now[p] === "{" && now[p + m - 1] === "}";
      const from = p + (wrapped ? 1 : 0);
      const to = p + m - (wrapped ? 1 : 0);
      if (to > from && !/[{}]|\\placeholder/.test(now.slice(from, to))) kept.push(text ? [from, to, "\\text{", "}"] : [from, to, "", ""]);
    }
    const moved = put.pos < 0 ? kept : kept.map(([a, b, open, close]) => (a >= put.pos ? [a + put.len, b + put.len, open, close] : [a, b, open, close]));
    return { tex, slots: moved, at };
  }

  //: **Whether a structure's boxes are all empty** (Word's rule: Backspace in an empty box selects the structure when
  //: nothing is typed in any box, and a second press removes it). `tex` is the structure's own TeX and `skeletons` the
  //: palette's templates (`#@` and `#?` are its boxes): a template's own fixed text, the `=1` of "sum from 1 to n" or
  //: the `\infty` of a limit, is not typed content, so a structure that reads like a template with every box empty is
  //: empty. Both are reduced to one shape (spaces, braces and the spelling of a bracket gone, a box a `P`). Without a
  //: template, a structure of only the plain frame commands and boxes (a fraction made with `/`, a script's boxes) is
  //: empty too; `strict` leaves that out, for a box that only stands beside a structure.
  function mathFieldHollow(tex, skeletons = [], strict = false) {
    const shaped = (text) =>
      String(text || "")
        .replace(/\\(left|right)\s*(\\[a-zA-Z]+|\\.|.)/g, "$1")
        .replace(/\\placeholder(\[[^\]]*\])?/g, "P")
        .replace(/#[@?]/g, "P")
        .replace(/\\\\/g, "|")
        .replace(/\\[,;: ]|[\s{}]/g, "");
    const shape = shaped(tex);
    if (!shape.includes("P")) return false;
    if (skeletons.some((skeleton) => shaped(skeleton) === shape)) return true;
    if (strict) return false;
    const rest = String(tex)
      .replace(/\\placeholder(\[[^\]]*\])?\{\}/g, "")
      .replace(/\\(begin|end)\{[a-zA-Z*]+\}/g, "")
      .replace(/\\(left|right)\s*(\\[a-zA-Z]+|\\.|.)/g, "")
      .replace(/\\(frac|dfrac|tfrac|binom|sqrt|text|mathrm)(?![a-zA-Z])/g, "")
      .replace(/[\s{}_^&[\]]|\\\\/g, "");
    return rest === "";
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
  //: MathLive's own custom properties, valued with the app's tokens.
  const MATH_FIELD_LOOK = {
    "--hue": "215",
    "--caret-color": "var(--accent)",
    "--selection-background-color": "color-mix(in srgb, var(--accent) 28%, transparent)",
    "--selection-color": "var(--text)",
    "--placeholder-color": "var(--accent)",
    "--placeholder-opacity": "0.75",
    "--smart-fence-color": "var(--muted)",
    "--text-font-family": "var(--font-sans, system-ui, sans-serif)",
  };

  function mathFieldCreate(label) {
    mathFieldConfigure();
    const field = new MathfieldElement();
    field.className = "math-field";
    for (const [name, value] of Object.entries(MATH_FIELD_LOOK)) field.style.setProperty(name, value);
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

  //: The LaTeX box and the button that shows it.
  function mathFieldLatexBox() {
    const toggle = document.createElement("button");
    toggle.type = "button";
    //: `quiet`: a toolbar action beside the Pin button, no edge (DESIGN.md, "The bordered ghost").
    toggle.className = "ghost quiet small math-field-toggle";
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
    //: The palette's templates as TeX, for `mathFieldHollow` (the palette's file is loaded with the editor, so none without it).
    const skeletons = () => {
      return typeof MATH_EDITOR_TEMPLATES === "undefined" ? [] : MATH_EDITOR_TEMPLATES.flatMap(([, , items]) => items.map((item) => item[1]));
    };

    //: **The structure a delete key is about to take apart, when every box in it is empty** (Word's equation editor: the
    //: first Backspace in an empty box selects the whole structure, the second removes it; INBOX 1664, the owner: "I cant
    //: delete these in the equations"). Returns `[from, to]` to select, or null when the key should do what it does: a
    //: structure with something typed in, a lone box, a selection of more than a box, or the structure already selected.
    //: The model is MathLive's own tree: an atom at offset `k` takes `(offset of the atom before it, k]`, boxes and
    //: scripts and all, and a big operator's body is a box beside it, so the two are one structure.
    const hollowRange = (backward) => {
      const model = field._mathfield?.model;
      if (!model) return null;
      const [from, to] = field.selection.ranges[0] || [0, 0];
      const isBox = (atom) => atom?.type === "placeholder";
      const tex = (a, b) => field.getValue(a, b, "latex");
      const start = (atom) => model.offsetOf(atom.leftSibling ?? atom);
      let atom;
      if (to > from) {
        if (to - from !== 1 || !isBox(model.at(to))) return null;
        atom = model.at(to);
      } else atom = model.at(backward ? to : to + 1);
      if (!atom) return null;
      //: A caret at the start of an empty branch is in its box; a box inside a structure stands for the structure.
      if (atom.type === "first" && atom.parent?.type !== "root") atom = atom.parent;
      if (isBox(atom) && atom.parent?.type !== "root") atom = atom.parent;
      if (!atom || atom.type === "first" || atom.type === "root") return null;
      if (!isBox(atom) && !tex(start(atom), model.offsetOf(atom)).includes("\\placeholder")) return null;
      //: The structure is a run of atoms beside each other that reads like a template with its boxes empty (a script is its base box and the script; a big operator its body box, and an integral's differential): the longest such run through the atom.
      const left = [];
      for (let at = atom.leftSibling; at && at.type !== "first" && left.length < 8; at = at.leftSibling) left.unshift(at);
      const right = [];
      for (let at = atom.rightSibling; at && right.length < 8; at = at.rightSibling) right.push(at);
      let best = null;
      for (let i = 0; i <= left.length; i += 1) {
        for (let j = 0; j <= right.length; j += 1) {
          const first = i ? left[left.length - i] : atom;
          const last = j ? right[j - 1] : atom;
          const a = start(first);
          const b = model.offsetOf(last);
          if (best && best.size >= i + j) continue;
          if (mathFieldHollow(tex(a, b), skeletons(), true)) best = { a, b, size: i + j };
        }
      }
      if (!best && !isBox(atom) && mathFieldHollow(tex(start(atom), model.offsetOf(atom)))) best = { a: start(atom), b: model.offsetOf(atom) };
      return !best || (best.a === from && best.b === to) ? null : [best.a, best.b];
    };
    //: The TeX as last settled and the boxes that were typed into (`mathFieldSlots`); a write from outside starts them over.
    let settled = "";
    let slots = [];
    let collapsed = true;
    const write = (next) => {
      field.setValue(mathFieldBoxes(next), { silenceNotifications: true });
      settled = field.getValue("latex");
      slots = [];
    };
    //: Select the `n`th box (counting from 0, left to right) so typing fills it; none and the caret stays where it is.
    const selectBox = (n) => {
      let seen = 0;
      for (let i = 0; i < field.lastOffset; i += 1) {
        if (!/^\\placeholder/.test(field.getValue(i, i + 1, "latex"))) continue;
        if (seen === n) {
          field.selection = { ranges: [[i, i + 1]] };
          return;
        }
        seen += 1;
      }
    };
    write(tex);
    box.value = tex;
    field.addEventListener("beforeinput", (event) => {
      collapsed = field.selectionIsCollapsed;
      //: A delete in an empty box, or beside a structure whose boxes are all empty, selects that structure first; the next one removes it.
      if (/^delete(Content|Word|Soft|Hard)?(Backward|Forward)$/.test(event.inputType || "")) {
        const range = hollowRange(/Backward$/.test(event.inputType));
        if (range) {
          event.preventDefault();
          field.selection = { ranges: [range] };
          return;
        }
      }
      //: MathLive can deliver an edit's `input` after the next edit has begun (a slow frame), so a character typed and deleted at once was never seen. For a deletion the TeX at this point is what the earlier edit made, so it is taken in first (a typing's own `beforeinput` comes mid-edit and says nothing). A selected box reads as empty here, so that moment is left to the `input` after it.
      if (!/^delete/.test(event.inputType || "")) return;
      const [from, to] = field.selection.ranges[0] || [0, 0];
      if (to > from && /^\\placeholder/.test(field.getValue(from, to, "latex"))) return;
      const pre = field.getValue("latex");
      if (pre === settled) return;
      slots = mathFieldSlots(settled, pre, slots, { restore: false }).slots;
      settled = pre;
    });
    field.addEventListener("input", () => {
      //: A slot emptied by typing and deleting, or cut, is a box again (INBOX 1538, 1584 d); the box takes the selection so typing fills it.
      const latex = field.getValue("latex");
      const got = mathFieldSlots(settled, latex, slots, { collapsed });
      const boxed = mathFieldBoxes(got.tex, true);
      if (boxed !== latex) {
        const at = field.position;
        field.setValue(boxed, { silenceNotifications: true });
        if (got.at >= 0) selectBox((got.tex.slice(0, got.at).match(/\\placeholder/g) || []).length);
        else field.selection = /^\\placeholder/.test(field.getValue(at, at + 1, "latex")) ? { ranges: [[at, at + 1]] } : { ranges: [[at, at]] };
      }
      const now = field.getValue("latex");
      slots = mathFieldSlots(boxed, now, mathFieldSlots(got.tex, boxed, got.slots, { restore: false }).slots, { restore: false }).slots;
      settled = now;
      box.value = mathFieldRead(field);
      onChange();
    });
    box.addEventListener("input", () => {
      write(box.value);
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
        write(next);
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

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { mathFieldConfigure, mathFieldPane, openMathInPlace });
})();
