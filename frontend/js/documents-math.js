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
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ϵ",
    varepsilon: "ε", zeta: "ζ", eta: "η", theta: "θ", vartheta: "ϑ", iota: "ι",
    kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", pi: "π", varpi: "ϖ",
    rho: "ρ", varrho: "ϱ", sigma: "σ", varsigma: "ς", tau: "τ", upsilon: "υ", phi: "ϕ",
    varphi: "φ", chi: "χ", psi: "ψ", omega: "ω",
    Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ",
    Pi: "Π", Sigma: "Σ", Upsilon: "Υ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
    infty: "∞", partial: "∂", nabla: "∇", emptyset: "∅", varnothing: "∅", ell: "ℓ",
    hbar: "ℏ", aleph: "ℵ", imath: "ı", jmath: "ȷ", wp: "℘", Re: "ℜ", Im: "ℑ",
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
    //: The palette's wider groups (INBOX 1579): relations, arrows, sets and logic, big operators and marks.
    ll: "≪", gg: "≫", simeq: "≃", cong: "≅", ncong: "≇", doteq: "≐", prec: "≺", succ: "≻", preceq: "⪯", succeq: "⪰",
    mid: "∣", nmid: "∤", models: "⊨", vdash: "⊢", dashv: "⊣", asymp: "≍", bowtie: "⋈", triangleq: "≜",
    nless: "≮", ngtr: "≯", nleq: "≰", ngeq: "≱",
    Leftarrow: "⇐", Leftrightarrow: "⇔", longrightarrow: "⟶", longleftarrow: "⟵", longleftrightarrow: "⟷",
    Longrightarrow: "⟹", Longleftarrow: "⟸", Longleftrightarrow: "⟺", longmapsto: "⟼", gets: "←",
    uparrow: "↑", downarrow: "↓", updownarrow: "↕", Uparrow: "⇑", Downarrow: "⇓",
    nearrow: "↗", searrow: "↘", swarrow: "↙", nwarrow: "↖", hookrightarrow: "↪", hookleftarrow: "↩",
    rightharpoonup: "⇀", leftharpoonup: "↼", rightleftharpoons: "⇌", iff: "⟺", implies: "⟹", impliedby: "⟸",
    ni: "∋", supseteq: "⊇", subsetneq: "⊊", supsetneq: "⊋", nsubseteq: "⊈", nsupseteq: "⊉", setminus: "∖",
    nexists: "∄", wedge: "∧", vee: "∨", lnot: "¬", top: "⊤", bot: "⊥", therefore: "∴", because: "∵",
    uplus: "⊎", sqcup: "⊔", sqcap: "⊓", sqsubseteq: "⊑", sqsupseteq: "⊒",
    bigoplus: "⨁", bigotimes: "⨂", bigvee: "⋁", bigwedge: "⋀", biguplus: "⨄",
    ominus: "⊖", odot: "⊙", ast: "∗", bullet: "∙", dagger: "†", ddagger: "‡", diamond: "⋄",
    triangle: "△", square: "□", blacksquare: "■", prime: "′", ddots: "⋱",
  };

  //: A named function is set upright, not italic: `sin x` is a function applied
  //: to a variable, and `s` times `i` times `n` times `x` is what it reads as
  //: when every letter is an identifier.
  const DOC_MATH_FUNCTIONS = [
    "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh", "log", "ln", "exp", "lim", "max", "min", "sup", "inf",
    "det", "dim", "gcd", "deg", "arg", "mod", "limsup", "liminf", "ker", "Pr",
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

  //: **What counts as a formula that failed** (audit 1102 DX18). The parser stays
  //: total (it still draws what it understood), but it now says so when it had
  //: to guess: the first thing it could not read is kept on the state and
  //: comes out as `problem` on the tree, so a reader is told rather than left
  //: with a lone "a" where `\frac{a}{` was typed.
  function docMathProblem(state, text) {
    if (state.problems && !state.problems.includes(text)) state.problems.push(text);
  }

  function docMathRow(kids) {
    return kids.length === 1 ? kids[0] : { tag: "mrow", kids };
  }

  //: One argument: a braced group, or the single token after the command.
  function docMathArgument(tokens, state) {
    const token = tokens[state.at];
    if (!token) {
      docMathProblem(state, "a command is missing what it applies to");
      return { tag: "mrow", kids: [] };
    }
    if (token.kind === "{") {
      state.at += 1;
      return docMathRow(docMathNodes(tokens, state, true));
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
  const DOC_MATH_ACCENTS = Object.assign(Object.create(null), { vec: "→", hat: "^", bar: "‾", overline: "‾", tilde: "~", dot: "˙", ddot: "¨", widehat: "^", widetilde: "~", overrightarrow: "→", overleftarrow: "←", acute: "´", grave: "`", breve: "˘", check: "ˇ", mathring: "˚" });
  //: `\mathbb{R}`: the double-struck letters a person writes sets with; any other letter stays as it is.
  const DOC_MATH_DOUBLE_STRUCK = Object.assign(Object.create(null), { N: "ℕ", Z: "ℤ", Q: "ℚ", R: "ℝ", C: "ℂ", H: "ℍ", P: "ℙ" });

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
    let ended = false;
    while (state.at < tokens.length) {
      const token = tokens[state.at];
      state.at += 1;
      const cmd = token.kind === "cmd" ? token.value : null;
      if (cmd === "end" && depth === 0) {
        docMathBracedName(tokens, state);
        ended = true;
        break;
      }
      if (token.kind === "{" || cmd === "begin") depth += 1;
      if (token.kind === "}" || cmd === "end") depth -= 1;
      const row = rows[rows.length - 1];
      if (depth === 0 && token.kind === "op" && token.value === "&") row.push([]);
      else if (depth === 0 && cmd === "\\") rows.push([[]]);
      else row[row.length - 1].push(token);
    }
    if (!ended) docMathProblem(state, "an environment has no \\end");
    return rows;
  }

  function docMathEnvironment(tokens, state) {
    const name = docMathBracedName(tokens, state);
    if (!(name in DOC_MATH_FENCES)) docMathProblem(state, `there is no environment called {${name}}`);
    const rows = docMathCells(tokens, state).filter((row) => row.some((cell) => cell.length));
    const table = {
      tag: "mtable",
      attrs: name === "cases" ? { columnalign: "left" } : undefined,
      kids: rows.map((row) => ({
        tag: "mtr",
        kids: row.map((cell) => ({ tag: "mtd", kids: [docMathRow(docMathNodes(cell, { at: 0, problems: state.problems }))] })),
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
    if (name === "underline") {
      const base = docMathArgument(tokens, state);
      return { tag: "munder", attrs: { accentunder: "true" }, kids: [base, { tag: "mo", text: "_" }] };
    }
    if (name === "overbrace" || name === "underbrace") {
      //: A label goes above or below the brace (`^{n}`, `_{n}`): `docMathNodes` reads the brace back off the base.
      const base = docMathArgument(tokens, state);
      const over = name === "overbrace";
      return { tag: over ? "mover" : "munder", kids: [base, { tag: "mo", text: over ? "\u23de" : "\u23df" }] };
    }
    if (name === "xrightarrow" || name === "xleftarrow") {
      //: The label sits on the arrow, which stretches to it.
      const label = docMathArgument(tokens, state);
      return { tag: "mover", kids: [{ tag: "mo", attrs: { stretchy: "true" }, text: DOC_MATH_OPERATORS[name === "xrightarrow" ? "rightarrow" : "leftarrow"] }, label] };
    }
    //: A box and a strike are a frame on the argument's own row, drawn by the documents CSS (`.math-boxed`,
    //: `.math-cancel`): Chromium has no `menclose`, and a class is what the CSP lets a formula carry.
    if (name === "boxed" || name === "cancel" || name === "bcancel" || name === "xcancel") {
      return { tag: "mrow", attrs: { class: name === "boxed" ? "math-boxed" : name === "cancel" ? "math-cancel" : `math-cancel math-${name}` }, kids: [docMathArgument(tokens, state)] };
    }
    if (name === "mathbb") {
      const letter = docMathArgument(tokens, state);
      return letter.tag === "mi" && letter.text in DOC_MATH_DOUBLE_STRUCK ? { tag: "mi", text: DOC_MATH_DOUBLE_STRUCK[letter.text] } : letter;
    }
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
    //: tenths understood should render nine tenths of the way, not fail; it
    //: is marked, though (`problem`), when the unknown thing is a command.
    if (/^[A-Za-z]/.test(name)) docMathProblem(state, `\\${name} is not a command this editor draws`);
    return { tag: "mi", text: name };
  }

  //: Integrals keep their limits beside the sign, as TeX does; the sums, products, unions and the named limits stack.
  const DOC_MATH_STACKED = new Set(["∑", "∏", "∐", "⋃", "⋂", "⨁", "⨂", "⋁", "⋀", "⨄", "lim", "max", "min", "sup", "inf", "limsup", "liminf", "det", "gcd", "Pr"]);
  function docMathLimitsBase(node) {
    return DOC_MATH_STACKED.has(node.text) && (node.tag === "mo" || (node.tag === "mi" && node.attrs && node.attrs.mathvariant === "normal"));
  }

  function docMathNodes(tokens, state, nested = false) {
    const kids = [];
    let closed = false;
    while (state.at < tokens.length) {
      const token = tokens[state.at];
      if (token.kind === "}") {
        state.at += 1;
        closed = true;
        break;
      }
      if (token.kind === "{") {
        state.at += 1;
        kids.push(docMathRow(docMathNodes(tokens, state, true)));
        continue;
      }
      if (token.kind === "^" || token.kind === "_") {
        state.at += 1;
        const base = kids.pop() || { tag: "mrow", kids: [] };
        const script = docMathArgument(tokens, state);
        const up = token.kind === "^";
        //: `x_i^2` is one element with two scripts, not a superscript on a
        //: subscript: written as the second it prints the 2 above the i.
        const brace = up ? "\u23de" : "\u23df";
        if (base.tag === (up ? "mover" : "munder") && base.kids[1] && base.kids[1].text === brace) {
          kids.push({ tag: base.tag, kids: [base, script] });
        } else if (base.limits && base.tag === (up ? "munder" : "mover")) {
          kids.push({ tag: "munderover", limits: true, kids: up ? [base.kids[0], base.kids[1], script] : [base.kids[0], script, base.kids[1]] });
        } else if (docMathLimitsBase(base)) {
          //: A big operator's limits stack above and below it, as TeX sets them: `movablelimits` lets the
          //: browser put them beside it again in a line of prose, where TeX does the same.
          const op = { tag: "mo", attrs: { movablelimits: "true" }, text: base.text };
          kids.push({ tag: up ? "mover" : "munder", limits: true, kids: [op, script] });
        } else if (base.tag === "msub" && up) {
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
    if (nested && !closed) docMathProblem(state, "a { is never closed");
    return kids;
  }

  //: The whole of the public surface: TeX in, a MathML tree out, as plain
  //: objects so this can be tested without a browser and built with
  //: `createElementNS` in one.
  function docMathTree(tex, display = false) {
    //: `\tag{1}` is TeX's own equation number, taken off the formula and kept
    //: beside the tree (`label`) for the display box to set at the right edge.
    //: Display only: an inline formula has nowhere to put one.
    //: `\label{k}` names a display equation and `\eqref{k}` (or `\ref{k}`) is its number in parentheses, from the map the page
    //: was indexed with (`docMathIndex`, `docMathUse`); an unknown key reads "(?)". A label is never drawn; with no `\tag` it
    //: supplies the number.
    const src = String(tex).replace(/\\(?:eqref|ref)\{([^{}]{1,40})\}/g, (all, key) => `\\text{(${DOC_MATH_LABELS.get(key.trim()) ?? "?"})}`);
    const named = /\\label\{([^{}]{1,40})\}/.exec(src);
    const clean = src.replace(/\\label\{[^{}]{0,40}\}/g, "");
    const found = display ? /\\tag\*?\{([^{}]{1,24})\}/.exec(clean) : null;
    const body = found ? clean.replace(found[0], "") : clean;
    const tokens = docMathTokens(body);
    const state = { at: 0, problems: [] };
    const kids = docMathNodes(tokens, state);
    //: A `}` with nothing open ends the parse early and drops the rest.
    if (state.at < tokens.length) docMathProblem(state, "a } has no { before it");
    return {
      problem: state.problems[0] || "",
      tag: "math",
      attrs: { display: display ? "block" : "inline" },
      kids: [docMathRow(kids.length ? kids : [{ tag: "mtext", text: "" }])],
      label: found ? found[1].trim() : display && named ? DOC_MATH_LABELS.get(named[1].trim()) || "" : "",
    };
  }

  //: The numbers a page's labels stand for: each `$$ ... $$` block with a `\label{k}` takes its `\tag{n}` or the next number
  //: (equations with a tag do not use one up). The caller (a page render) hands the map to `docMathUse` before it draws.
  let DOC_MATH_LABELS = new Map();
  //: The numbered blocks of a page in reading order: each `$$ ... $$` and each `\begin{equation} ... \end{equation}`
  //: (the latter with its `eq-auto-N` key, N counting those, starred ones left out).
  function docMathBlocks(page) {
    const blocks = [];
    //: Blocks found with indexOf, not a lazy regex: a run of `$` with no closing pair would be rescanned from every start.
    for (let open = page.indexOf("$$"); open >= 0; ) {
      const close = page.indexOf("$$", open + 2);
      if (close < 0) break;
      if (close > open + 2) blocks.push({ at: open, body: page.slice(open + 2, close), auto: "" });
      open = page.indexOf("$$", close + 2);
    }
    let n = 0;
    for (const found of page.matchAll(/^[ \t]*\\begin\{equation\}([\s\S]*?)\\end\{equation\}/gm)) {
      n += 1;
      blocks.push({ at: found.index, body: found[1], auto: `eq-auto-${n}` });
    }
    return blocks.sort((a, b) => a.at - b.at);
  }
  function docMathIndex(text) {
    const labels = new Map();
    let next = 0;
    for (const { body, auto } of docMathBlocks(String(text ?? ""))) {
      const key = /\\label\{([^{}]{1,40})\}/.exec(body)?.[1].trim();
      const dup = key && labels.has(key);
      if ((!key && !auto) || (dup && !auto)) continue;
      const tag = /\\tag\*?\{([^{}]{1,24})\}/.exec(body)?.[1].trim();
      const number = tag || String((next += 1));
      if (key && !dup) labels.set(key, number);
      if (auto) labels.set(auto, number);
    }
    return labels;
  }
  function docMathUse(labels) {
    DOC_MATH_LABELS = labels instanceof Map ? labels : new Map();
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

  // DOC-EQUATION-BEGIN (tests/test_doc_equation_env.py runs this in node)
  //: `\begin{equation} ... \end{equation}` is a display equation that numbers
  //: itself, `equation*` is the same without a number (LaTeX's rule). The block
  //: opens at the start of a line and ends at the line with `\end{...}` (or on
  //: the same line). A numbered one is handed on with a `\label{eq-auto-N}` the
  //: page index (`docMathIndex`) knows, N counting the numbered openers before
  //: it; one that has its own `\label` or `\tag` keeps it.
  //:
  //: **Taken in front of the boot script's door** (`mdMathBlockFrom`,
  //: markdown.js) when this file loads, rather than as lines in it: the boot
  //: scripts are on a byte ratchet and this is only needed where math draws. A
  //: page with no math module loaded shows the block as the text it is.
  function docMathEquationFrom(lines, start) {
    const open = /^\s*\\begin\{(equation\*?)\}(.*)$/.exec(String(lines[start] || ""));
    if (!open) return null;
    const close = `\\end{${open[1]}}`;
    const body = [];
    let tail = open[2];
    for (let i = start; i < lines.length; i += 1, tail = lines[i] ?? "") {
      const at = tail.indexOf(close);
      if (at >= 0) {
        body.push(tail.slice(0, at));
        return { tex: docMathEquationLabel(lines, start, open[1], body.join("\n").trim()), end: i + 1 };
      }
      body.push(tail);
    }
    return null;
  }

  function docMathEquationLabel(lines, start, name, tex) {
    if (name.endsWith("*") || /\\(?:label|tag)\{/.test(tex)) return tex;
    let before = 0;
    for (let i = 0; i < start; i += 1) if (/^\s*\\begin\{equation\}/.test(String(lines[i] || ""))) before += 1;
    return `${tex} \\label{eq-auto-${before + 1}}`;
  }

  const mdDoor = window.mdMathBlockFrom;
  if (mdDoor) window.mdMathBlockFrom = (lines, start) => docMathEquationFrom(lines, start) || mdDoor(lines, start);
  // DOC-EQUATION-END

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
    const drawn = docMathNumbered(tree, docMathElement(tree));
    if (!tree.problem) return drawn;
    //: **A formula the parser had to guess at says so** (audit 1102 DX18): an
    //: error tint and a title naming the first thing it could not read, on one
    //: wrapper so the Live widget, the Read view and a note card all get it
    //: from here. `title` sits on the span, not on the MathML element, which
    //: browsers do not give a tooltip.
    const mark = document.createElement("span");
    mark.className = "md-math-error";
    mark.title = `Not drawn as written: ${tree.problem}.`;
    mark.append(drawn);
    return mark;
  }

  function docMathNumbered(tree, math) {
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
  //: The page's equation numbers ride on the renderer rather than take two more names in the shared scope.
  docMathRender.labels = {
    index: docMathIndex,
    use: docMathUse,
    //: A render of its own (a note card, a chat answer) indexes its own labels, only when it has some (navigation.js, boot-size budget).
    page: (text) => !docMathRender.labels.held && /\\(?:label|eqref|ref)\{|\\begin\{equation\}/.test(text) && docMathUse(docMathIndex(text)),
    //: True while a document renders its pieces (columns): each piece keeps the whole page's map instead of indexing its own text.
    held: false,
  };

  //: **Fenced blocks drawn by a lazy module**: the ```graph block (documents-graph.js; DOCUMENTS_PLAN 16) and the ```base block
  //: (documents-base.js; gap row 6). Read swaps each fence for its figure, and Live draws one the caret is outside of, through a
  //: state field for the reason the mermaid fence gives (a replace across line breaks may not come from a plugin). The figure's own
  //: clicks and drags are the figure's: the pencil on its corner puts the caret in the text.
  const FENCES = {
    graph: { module: "docGraph", cls: "md-graph", wrap: "cm-md-graph-wrap", pending: "md-graph-pending", edit: "dg-edit", height: 420, fill: (figure, source) => docMathRender.graph.fill(figure, source) },
    base: { module: "docBase", cls: "md-base", wrap: "cm-md-base-wrap", pending: "md-base-pending", edit: "db-edit", height: 180, fill: (figure, source, write) => docMathRender.base.fill(figure, source, write) },
  };
  const fenceBlocks = (lang) => (text) =>
    [...text.matchAll(new RegExp("^```[ \\t]*" + lang + "\\b[^\\n]*\\n([\\s\\S]*?)\\n```[ \\t]*$", "gm"))].map((m) => ({ from: m.index, to: m.index + m[0].length, source: m[1] }));
  //: A changed fence goes back into the document: the Live view's own editor when `view` is given, else Read's surface (the one
  //: a ticked task writes through). `pick` names the block among the document's fences of that language.
  const fenceWrite = (lang, pick, next, view) => {
    const surface = view || window.docSurface?.();
    const text = view ? view.state.doc.toString() : surface?.text;
    const block = text == null ? null : pick(fenceBlocks(lang)(text));
    if (!block) return;
    const from = block.from + text.slice(block.from).indexOf("\n") + 1;
    if (view) view.dispatch({ changes: { from, to: from + block.source.length, insert: next } });
    else surface.replaceRange(from, from + block.source.length, next);
  };
  const fenceIn = (lang) => (container) => {
    const spec = FENCES[lang];
    const codes = [...container.querySelectorAll(`.code-block code[data-lang="${lang}"]`)];
    if (!codes.length) return;
    ensureModule(spec.module).then((ok) => {
      for (const code of ok ? codes : []) {
        const block = code.closest(".code-block");
        if (!block?.isConnected) continue;
        const figure = document.createElement("figure");
        figure.className = spec.cls;
        //: A fence that draws nothing stays the code it is, with the reasons under it.
        const n = codes.indexOf(code);
        if (spec.fill(figure, code.textContent, (next) => fenceWrite(lang, (blocks) => (blocks[n]?.source.trim() === code.textContent.trim() ? blocks[n] : null), next))) block.replaceWith(figure);
        else block.after(figure);
      }
    });
  };
  const fenceFieldCache = {};
  const fenceField = (lang) => (CM) => {
    if (fenceFieldCache[lang]) return fenceFieldCache[lang];
    const spec = FENCES[lang];
    const { StateField } = CM.state;
    const { Decoration, EditorView, WidgetType } = CM.view;
    class DocFenceWidget extends WidgetType {
      constructor(source) {
        super();
        this.source = source;
      }
      //: The source alone: a key typed above a block must not draw it again and lose its sliders.
      eq(other) {
        return other.source === this.source;
      }
      get estimatedHeight() {
        return spec.height;
      }
      ignoreEvent() {
        return true;
      }
      toDOM(view) {
        const wrap = document.createElement("div");
        wrap.className = spec.wrap;
        const figure = document.createElement("figure");
        figure.className = `${spec.cls} cm-${spec.cls} ${spec.pending}`;
        const edit = smallButton("ph:pencil-simple", `Edit the ${lang}'s text`, () => {
          view.dispatch({ selection: { anchor: Math.min(view.posAtDOM(wrap) + 4, view.state.doc.length) } });
          view.focus();
        });
        edit.classList.add(spec.edit, "icon-only");
        wrap.append(figure, edit);
        ensureModule(spec.module).then((ok) => {
          if (!ok) return;
          figure.classList.remove(spec.pending);
          spec.fill(figure, this.source, (next) => fenceWrite(lang, (blocks) => blocks.find((b) => b.from === view.posAtDOM(wrap)), next, view));
          view.requestMeasure();
        });
        return wrap;
      }
    }
    //: The fences once per text, as the mermaid field does: a caret move rescanned the whole document.
    const blocksOf = new WeakMap();
    const find = fenceBlocks(lang);
    const build = (state) => {
      let blocks = blocksOf.get(state.doc);
      if (!blocks) {
        //: Through the Documents file's cached reader where it is loaded (a long text read twice per keystroke is the cost it avoids).
        const text = window.docStr ? window.docStr(state.doc) : state.doc.sliceString(0);
        blocks = new RegExp("```[ \\t]*" + lang).test(text) ? find(text) : [];
        blocksOf.set(state.doc, blocks);
      }
      const ranges = blocks
        .filter((block) => !docLiveSpanTouched.anchorIn(state.selection.ranges, block.from, block.to))
        .map((block) => Decoration.replace({ widget: new DocFenceWidget(block.source), block: true }).range(block.from, block.to));
      return ranges.length ? Decoration.set(ranges, true) : Decoration.none;
    };
    fenceFieldCache[lang] = StateField.define({
      create: (state) => build(state),
      update: (value, tr) => (tr.docChanged || tr.selection ? build(tr.state) : value),
      provide: (field) => EditorView.decorations.from(field),
    });
    return fenceFieldCache[lang];
  };
  Object.assign(docMathRender, {
    graphBlocks: fenceBlocks("graph"),
    graphIn: fenceIn("graph"),
    graphField: fenceField("graph"),
    baseBlocks: fenceBlocks("base"),
    baseIn: fenceIn("base"),
    baseField: fenceField("base"),
  });
})();
