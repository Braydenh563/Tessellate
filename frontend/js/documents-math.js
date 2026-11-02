// documents-math.js: the TeX subset and its MathML renderer (split out of
// documents.js, audit 1031 DC13 remainder).
//
// What is here: the small, total TeX parser (`docMathTree`, bracketed by
// `DOC-MATH-BEGIN`/`END` for `tests/test_doc_math.py`, which runs it in node),
// `docMathLooksLikeMath` (the rule that tells a `$...$` span from prose) and the
// MathML renderer (`docMathRender`). What stayed in documents.js: nothing that
// reads from here at load; the Live decorations in documents-cm.js and the
// markdown renderer call `docMathLooksLikeMath` and `docMathRender` from inside
// functions.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: this file's own top level declares tables and
// functions and reads nothing from documents.js. One closure; what other files
// call is the `Object.assign` at the foot.
(() => {
  // =============================================================================
  // Math: a small TeX subset rendered as MathML (DOCUMENTS_PLAN Phase 3 item 2)
  // =============================================================================
  //
  // **No KaTeX, and the plan is explicit about it.** The reasons are worth
  // keeping next to the code rather than in the plan: KaTeX is 280 KB of script
  // and a megabyte of fonts for a notebook whose documents are notes and plans,
  // it wants a stylesheet this app's CSP would have to be widened for, and every
  // browser this app runs in has rendered MathML natively since 2023. What a
  // local-first notebook needs is the arithmetic, the greek, a fraction, a root,
  // a sum and a sub/superscript, which is what this does.
  //
  // The parser is deliberately small and deliberately total: anything it does
  // not understand comes out as the text that was typed rather than as an error,
  // because an editor that turns a formula it half-knows into a red box is worse
  // than one that leaves it alone. `tests/test_doc_math.py` runs it in node over
  // the shapes this file claims to handle.

  // DOC-MATH-BEGIN

  //: The symbols, by what they are rather than by how they look: a greek letter
  //: is an identifier (`mi`, italic like any variable) and an operator is an
  //: operator (`mo`, spaced like one). Getting that split wrong is what makes
  //: hand-rolled math read as a string of glyphs.
  const DOC_MATH_LETTERS = {
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε",
    varepsilon: "ε", zeta: "ζ", eta: "η", theta: "θ", iota: "ι",
    kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", pi: "π",
    rho: "ρ", sigma: "σ", tau: "τ", upsilon: "υ", phi: "φ",
    varphi: "φ", chi: "χ", psi: "ψ", omega: "ω",
    Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ",
    Pi: "Π", Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
    infty: "∞", partial: "∂", nabla: "∇", emptyset: "∅", ell: "ℓ",
  };

  const DOC_MATH_OPERATORS = {
    times: "×", div: "÷", cdot: "⋅", pm: "±", mp: "∓",
    le: "≤", leq: "≤", ge: "≥", geq: "≥", ne: "≠", neq: "≠",
    approx: "≈", equiv: "≡", propto: "∝", sim: "∼",
    to: "→", rightarrow: "→", leftarrow: "←", Rightarrow: "⇒",
    leftrightarrow: "↔", mapsto: "↦",
    in: "∈", notin: "∉", subset: "⊂", subseteq: "⊆", supset: "⊃",
    cup: "∪", cap: "∩", forall: "∀", exists: "∃", neg: "¬",
    land: "∧", lor: "∨", oplus: "⊕", otimes: "⊗", circ: "∘",
    star: "⋆", perp: "⊥", parallel: "∥", angle: "∠", degree: "°",
    ldots: "…", dots: "…", cdots: "⋯", vdots: "⋮",
    sum: "∑", prod: "∏", int: "∫", iint: "∬", oint: "∮",
    bigcup: "⋃", bigcap: "⋂", sqrt: "√", iiint: "∭", coprod: "∐",
    lfloor: "⌊", rfloor: "⌋", lceil: "⌈", rceil: "⌉", langle: "⟨", rangle: "⟩",
  };

  //: A named function is set upright, not italic: `sin x` is a function applied
  //: to a variable, and `s` times `i` times `n` times `x` is what it reads as
  //: when every letter is an identifier.
  const DOC_MATH_FUNCTIONS = [
    "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh", "log", "ln", "exp", "lim", "max", "min", "sup", "inf",
    "det", "dim", "gcd", "deg", "arg", "mod",
  ];

  //: Text, taken raw, because the tokeniser below throws whitespace away and
  //: `\text{a b}` is the one place the spaces are the point.
  const DOC_MATH_RAW_COMMANDS = ["text", "mathrm", "operatorname", "mathbf", "textbf"];

  function docMathTokens(tex) {
    const src = String(tex == null ? "" : tex);
    const tokens = [];
    let at = 0;
    while (at < src.length) {
      const ch = src[at];
      if (/\s/.test(ch)) {
        at += 1;
        continue;
      }
      if (ch === "\\") {
        const command = /^\\([A-Za-z]+|.)/.exec(src.slice(at));
        if (!command) break;
        at += command[0].length;
        const name = command[1];
        if (DOC_MATH_RAW_COMMANDS.includes(name) && src[at] === "{") {
          let depth = 1;
          let end = at + 1;
          while (end < src.length && depth > 0) {
            if (src[end] === "{") depth += 1;
            else if (src[end] === "}") depth -= 1;
            if (depth > 0) end += 1;
          }
          tokens.push({ kind: "text", value: src.slice(at + 1, end), bold: name === "mathbf" || name === "textbf" });
          at = end + 1;
          continue;
        }
        tokens.push({ kind: "cmd", value: name });
        continue;
      }
      const number = /^[0-9]+(?:\.[0-9]+)?/.exec(src.slice(at));
      if (number) {
        tokens.push({ kind: "num", value: number[0] });
        at += number[0].length;
        continue;
      }
      if (/[A-Za-z]/.test(ch)) {
        tokens.push({ kind: "id", value: ch });
        at += 1;
        continue;
      }
      if (ch === "{" || ch === "}" || ch === "^" || ch === "_") {
        tokens.push({ kind: ch });
        at += 1;
        continue;
      }
      tokens.push({ kind: "op", value: ch });
      at += 1;
    }
    return tokens;
  }

  function docMathRow(kids) {
    return kids.length === 1 ? kids[0] : { tag: "mrow", kids };
  }

  //: One argument: a braced group, or the single token after the command.
  function docMathArgument(tokens, state) {
    const token = tokens[state.at];
    if (!token) return { tag: "mrow", kids: [] };
    if (token.kind === "{") {
      state.at += 1;
      return docMathRow(docMathNodes(tokens, state));
    }
    state.at += 1;
    return docMathToken(token, tokens, state);
  }

  function docMathToken(token, tokens, state) {
    if (token.kind === "num") return { tag: "mn", text: token.value };
    if (token.kind === "id") return { tag: "mi", text: token.value };
    if (token.kind === "text") {
      //: `mathvariant`, never a `style` attribute: this app's CSP refuses inline
      //: styles, so a bold done that way would be a silent no-op.
      return token.bold
        ? { tag: "mtext", attrs: { mathvariant: "bold" }, text: token.value }
        : { tag: "mtext", text: token.value };
    }
    if (token.kind === "cmd") return docMathCommand(token.value, tokens, state);
    return { tag: "mo", text: token.value };
  }

  //: **Matrices and case splits** (DOCUMENTS_PLAN row 16, the equation
  //: editor's templates). The fences each environment wears, open then close;
  //: `matrix` has none and `cases` only the brace on its left.
  const DOC_MATH_FENCES = Object.assign(Object.create(null), {
    matrix: ["", ""], pmatrix: ["(", ")"], bmatrix: ["[", "]"], Bmatrix: ["{", "}"],
    vmatrix: ["|", "|"], Vmatrix: ["‖", "‖"], cases: ["{", ""], aligned: ["", ""], array: ["", ""],
  });

  //: Accents over their argument, as `mover`: what each one draws.
  const DOC_MATH_ACCENTS = Object.assign(Object.create(null), { vec: "→", hat: "^", bar: "‾", overline: "‾", tilde: "~", dot: "˙", ddot: "¨" });

  //: The three tables below have no prototype: a name typed in a note (`\toString`,
  //: `\begin{constructor}`) must not find an Object.prototype member.
  //: TeX's spaces, as their width in ems: `\,` was a printed comma before.
  const DOC_MATH_SPACES = Object.assign(Object.create(null), { ",": "0.17em", ":": "0.22em", ";": "0.28em", "!": "0em", quad: "1em", qquad: "2em" });

  //: The letters of a braced name (`{pmatrix}`), consumed; "" when there is none.
  function docMathBracedName(tokens, state) {
    if (!tokens[state.at] || tokens[state.at].kind !== "{") return "";
    state.at += 1;
    let name = "";
    while (state.at < tokens.length && tokens[state.at].kind !== "}") {
      name += tokens[state.at].value || "";
      state.at += 1;
    }
    if (state.at < tokens.length) state.at += 1;
    return name;
  }

  //: The tokens of one environment's body split into rows of cells, at `&`
  //: and `\\` outside any brace or inner environment; stops after its `\end`.
  function docMathCells(tokens, state) {
    const rows = [[[]]];
    let depth = 0;
    while (state.at < tokens.length) {
      const token = tokens[state.at];
      state.at += 1;
      const cmd = token.kind === "cmd" ? token.value : null;
      if (cmd === "end" && depth === 0) {
        docMathBracedName(tokens, state);
        break;
      }
      if (token.kind === "{" || cmd === "begin") depth += 1;
      if (token.kind === "}" || cmd === "end") depth -= 1;
      const row = rows[rows.length - 1];
      if (depth === 0 && token.kind === "op" && token.value === "&") row.push([]);
      else if (depth === 0 && cmd === "\\") rows.push([[]]);
      else row[row.length - 1].push(token);
    }
    return rows;
  }

  function docMathEnvironment(tokens, state) {
    const name = docMathBracedName(tokens, state);
    const rows = docMathCells(tokens, state).filter((row) => row.some((cell) => cell.length));
    const table = {
      tag: "mtable",
      attrs: name === "cases" ? { columnalign: "left" } : undefined,
      kids: rows.map((row) => ({
        tag: "mtr",
        kids: row.map((cell) => ({ tag: "mtd", kids: [docMathRow(docMathNodes(cell, { at: 0 }))] })),
      })),
    };
    const [open, close] = DOC_MATH_FENCES[name] || ["", ""];
    if (!open && !close) return table;
    const kids = [];
    if (open) kids.push({ tag: "mo", text: open });
    kids.push(table);
    if (close) kids.push({ tag: "mo", text: close });
    return { tag: "mrow", kids };
  }

  //: The commands that take arguments and draw a structure, other than the
  //: fraction and the root; null when `name` is not one of them.
  function docMathStructure(name, tokens, state) {
    if (name === "begin") return docMathEnvironment(tokens, state);
    if (name === "end") {
      docMathBracedName(tokens, state);
      return { tag: "mrow", kids: [] };
    }
    if (name === "binom") {
      const top = docMathArgument(tokens, state);
      const bottom = docMathArgument(tokens, state);
      return { tag: "mrow", kids: [{ tag: "mo", text: "(" }, { tag: "mfrac", attrs: { linethickness: "0" }, kids: [top, bottom] }, { tag: "mo", text: ")" }] };
    }
    if (DOC_MATH_ACCENTS[name]) {
      const base = docMathArgument(tokens, state);
      return { tag: "mover", attrs: { accent: "true" }, kids: [base, { tag: "mo", text: DOC_MATH_ACCENTS[name] }] };
    }
    if (name in DOC_MATH_SPACES) return { tag: "mspace", attrs: { width: DOC_MATH_SPACES[name] } };
    return null;
  }

  function docMathCommand(name, tokens, state) {
    const structure = docMathStructure(name, tokens, state);
    if (structure) return structure;
    if (name === "frac" || name === "dfrac" || name === "tfrac") {
      const top = docMathArgument(tokens, state);
      const bottom = docMathArgument(tokens, state);
      return { tag: "mfrac", kids: [top, bottom] };
    }
    if (name === "sqrt") {
      //: `\sqrt[3]{x}`: the index is in brackets, which the tokeniser has no
      //: special case for, so it arrives as the operators `[` and `]`.
      if (tokens[state.at] && tokens[state.at].kind === "op" && tokens[state.at].value === "[") {
        state.at += 1;
        const index = [];
        while (
          state.at < tokens.length &&
          !(tokens[state.at].kind === "op" && tokens[state.at].value === "]")
        ) {
          const token = tokens[state.at];
          state.at += 1;
          index.push(docMathToken(token, tokens, state));
        }
        if (state.at < tokens.length) state.at += 1;
        return { tag: "mroot", kids: [docMathArgument(tokens, state), docMathRow(index)] };
      }
      return { tag: "msqrt", kids: [docMathArgument(tokens, state)] };
    }
    if (name === "left" || name === "right") {
      //: The delimiter that follows carries the meaning; the sizing command
      //: itself is MathML's job rather than the author's.
      const next = tokens[state.at];
      if (!next) return { tag: "mrow", kids: [] };
      state.at += 1;
      if (next.kind === "cmd" && next.value === ".") return { tag: "mrow", kids: [] };
      return { tag: "mo", text: DOC_MATH_OPERATORS[next.value] || next.value || "" };
    }
    if (DOC_MATH_LETTERS[name]) return { tag: "mi", text: DOC_MATH_LETTERS[name] };
    if (DOC_MATH_OPERATORS[name]) return { tag: "mo", text: DOC_MATH_OPERATORS[name] };
    if (DOC_MATH_FUNCTIONS.includes(name)) return { tag: "mi", attrs: { mathvariant: "normal" }, text: name };
    if (name === "{" || name === "}" || name === "|") return { tag: "mo", text: name };
    //: Anything unknown comes back as what was typed. A formula that is nine
    //: tenths understood should render nine tenths of the way, not fail.
    return { tag: "mi", text: name };
  }

  function docMathNodes(tokens, state) {
    const kids = [];
    while (state.at < tokens.length) {
      const token = tokens[state.at];
      if (token.kind === "}") {
        state.at += 1;
        break;
      }
      if (token.kind === "{") {
        state.at += 1;
        kids.push(docMathRow(docMathNodes(tokens, state)));
        continue;
      }
      if (token.kind === "^" || token.kind === "_") {
        state.at += 1;
        const base = kids.pop() || { tag: "mrow", kids: [] };
        const script = docMathArgument(tokens, state);
        const up = token.kind === "^";
        //: `x_i^2` is one element with two scripts, not a superscript on a
        //: subscript: written as the second it prints the 2 above the i.
        if (base.tag === "msub" && up) {
          kids.push({ tag: "msubsup", kids: [base.kids[0], base.kids[1], script] });
        } else if (base.tag === "msup" && !up) {
          kids.push({ tag: "msubsup", kids: [base.kids[0], script, base.kids[1]] });
        } else {
          kids.push({ tag: up ? "msup" : "msub", kids: [base, script] });
        }
        continue;
      }
      state.at += 1;
      kids.push(docMathToken(token, tokens, state));
    }
    return kids;
  }

  //: The whole of the public surface: TeX in, a MathML tree out, as plain
  //: objects so this can be tested without a browser and built with
  //: `createElementNS` in one.
  function docMathTree(tex, display = false) {
    //: `\tag{1}` is TeX's own equation number, taken off the formula and kept
    //: beside the tree (`label`) for the display box to set at the right edge.
    //: Display only: an inline formula has nowhere to put one.
    const found = display ? /\\tag\*?\{([^{}]{1,24})\}/.exec(tex) : null;
    const body = found ? tex.replace(found[0], "") : tex;
    const kids = docMathNodes(docMathTokens(body), { at: 0 });
    return {
      tag: "math",
      attrs: { display: display ? "block" : "inline" },
      kids: [docMathRow(kids.length ? kids : [{ tag: "mtext", text: "" }])],
      label: found ? found[1].trim() : "",
    };
  }

  //: **What counts as math and what is a price.** `$` is a currency sign far
  //: more often than it is a delimiter in a notebook, so the rule is the one
  //: Obsidian and Typora use, plus one guard of this app's own: no space just
  //: inside either delimiter (which is what excludes "$5 and $10"), and the
  //: content has to contain something mathematical rather than being a bare
  //: number with an operator stuck to it (which is what excludes "$5-$10").
  const DOC_MATH_MEANINGFUL = /[A-Za-z\\^_=+]/;

  function docMathLooksLikeMath(body) {
    const text = String(body == null ? "" : body);
    if (!text || /^\s/.test(text) || /\s$/.test(text)) return false;
    return DOC_MATH_MEANINGFUL.test(text);
  }

  // DOC-MATH-END

  //: The tree as elements. MathML is its own namespace: built with
  //: `createElement` the tags are unknown HTML elements, which render as their
  //: own text content in a straight line and look exactly like a renderer that
  //: half-works.
  const DOC_MATHML_NS = "http://www.w3.org/1998/Math/MathML";

  function docMathElement(node) {
    const el = document.createElementNS(DOC_MATHML_NS, node.tag);
    for (const [name, value] of Object.entries(node.attrs || {})) el.setAttribute(name, value);
    if (node.text != null) el.textContent = node.text;
    for (const kid of node.kids || []) el.appendChild(docMathElement(kid));
    return el;
  }

  function docMathRender(tex, display = false) {
    const tree = docMathTree(tex, display);
    const math = docMathElement(tree);
    if (!tree.label) return math;
    //: A numbered equation: the formula centred, its number at the right edge.
    const box = document.createElement("span");
    box.className = "md-math-numbered";
    const number = document.createElement("span");
    number.className = "md-math-number";
    number.textContent = `(${tree.label})`;
    box.append(math, number);
    return box;
  }

  //: The file's whole surface: what documents-cm.js, markdown.js and navigation.js call.
  Object.assign(window, { docMathLooksLikeMath, docMathRender });
})();
