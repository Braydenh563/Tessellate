// documents-graph.js: the ```graph block (DOCUMENTS_PLAN gap row 16; the owner, 2026-10-26: "a graph block, y = f(x),
// sliders, lazy-loaded"). A fence of lines is drawn as a plot you can move: one curve per `y = ...` line, one slider per
// `name = 1 [0, 5]` line, `x: -10..10` and `y: -3..3` for the window, `title: ...`. No eval: the expression is read by
// the small parser below, so a document from anywhere cannot run code. Lazy: `LAZY_MODULES.docGraph`, registered at the
// foot of documents-math.js, which also draws the Live figure and the Read view's swap and calls `docMathRender.graph.*`.
// Everything is a property of `docMathRender.graph`, so the file adds no global name.
(() => {
  // DOC-GRAPH-BEGIN (tests/test_doc_graph.py runs this region in node)
  const FUNCS = {
    sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
    sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh, sqrt: Math.sqrt, cbrt: Math.cbrt, abs: Math.abs,
    ln: Math.log, log: Math.log10, log10: Math.log10, log2: Math.log2, exp: Math.exp, floor: Math.floor,
    ceil: Math.ceil, round: Math.round, sign: Math.sign, min: Math.min, max: Math.max, pow: Math.pow,
    sec: (v) => 1 / Math.cos(v), csc: (v) => 1 / Math.sin(v), cot: (v) => 1 / Math.tan(v),
    mod: (a, b) => ((a % b) + b) % b,
  };
  const CONSTS = { pi: Math.PI, tau: 2 * Math.PI, e: Math.E };
  const MAX_CURVES = 6;
  const MAX_PARAMS = 8;

  //: The writing a person types in a note (x², π, √, ×) as the plain form the reader takes.
  function plain(text) {
    return String(text)
      .replace(/²/g, "^2").replace(/³/g, "^3").replace(/π/g, " pi ").replace(/√/g, " sqrt ")
      .replace(/[×·]/g, "*").replace(/÷/g, "/").replace(/[−–]/g, "-");
  }

  //: **`compile(text, names)`**: the function `(vars) => number` for one expression, `names` being the variables it
  //: may read (`x` and the sliders). Throws an Error whose message is the sentence shown under the plot.
  function compile(text, names) {
    const tokens = [];
    const re = /\s*(?:(\d*\.?\d+)|([A-Za-z]+)|(.))/y;
    const source = plain(text);
    for (let m = re.exec(source); m && m.index < source.length; m = re.exec(source)) {
      if (m[1] !== undefined) tokens.push({ n: Number(m[1]) });
      else if (m[2] !== undefined) tokens.push({ id: names.has(m[2]) ? m[2] : m[2].toLowerCase() });
      else tokens.push({ op: m[3] });
    }
    let at = 0;
    const next = () => tokens[at];
    const op = (symbol) => next()?.op === symbol;
    const operand = () => next() && (next().n !== undefined || next().id !== undefined || next().op === "(");
    const fail = (message) => {
      throw new Error(message);
    };
    const expect = (symbol) => (op(symbol) ? at++ : fail(`Missing "${symbol}".`));

    function sum() {
      let left = product();
      while (op("+") || op("-")) {
        const minus = tokens[at++].op === "-";
        const a = left;
        const b = product();
        left = minus ? (v) => a(v) - b(v) : (v) => a(v) + b(v);
      }
      return left;
    }
    function product() {
      let left = unary();
      for (;;) {
        if (op("*") || op("/")) {
          const divide = tokens[at++].op === "/";
          const a = left;
          const b = unary();
          left = divide ? (v) => a(v) / b(v) : (v) => a(v) * b(v);
        } else if (operand()) {
          //: "2x", "2(x+1)", "a b": a product with no sign.
          const a = left;
          const b = unary();
          left = (v) => a(v) * b(v);
        } else return left;
      }
    }
    function unary() {
      if (op("-")) {
        at++;
        const a = unary();
        return (v) => -a(v);
      }
      if (op("+")) {
        at++;
        return unary();
      }
      return power();
    }
    function power() {
      const base = primary();
      if (!op("^")) return base;
      at++;
      const exponent = unary();
      return (v) => Math.pow(base(v), exponent(v));
    }
    //: The argument of a function written without brackets: "sin x", and "sin 2x" as sin(2x); "sin x cos x" is two functions.
    function chain() {
      const coefficient = next()?.n !== undefined;
      let left = unary();
      while (coefficient && operand() && next().n === undefined) {
        const a = left;
        const b = unary();
        left = (v) => a(v) * b(v);
      }
      return left;
    }
    function primary() {
      const token = tokens[at++];
      if (!token) return fail("The line ends too soon.");
      if (token.n !== undefined) return () => token.n;
      if (token.op === "(") {
        const inner = sum();
        expect(")");
        return inner;
      }
      if (token.id === undefined) return fail(`Unexpected "${token.op}".`);
      const id = token.id;
      if (Object.hasOwn(FUNCS, id) && !names.has(id)) {
        const f = FUNCS[id];
        if (!op("(")) {
          const arg = chain();
          return (v) => f(arg(v));
        }
        at++;
        const args = [sum()];
        while (op(",")) {
          at++;
          args.push(sum());
        }
        expect(")");
        return args.length === 1 ? (v) => f(args[0](v)) : (v) => f(...args.map((a) => a(v)));
      }
      if (names.has(id)) return (v) => v[id];
      if (Object.hasOwn(CONSTS, id)) return () => CONSTS[id];
      //: "ax" is a times x when every letter is a name of its own.
      if (id.length > 1 && [...id].every((c) => names.has(c) || Object.hasOwn(CONSTS, c))) {
        const parts = [...id].map((c) => (names.has(c) ? (v) => v[c] : () => CONSTS[c]));
        return (v) => parts.reduce((total, part) => total * part(v), 1);
      }
      return fail(`"${id}" is not a function or a slider here.`);
    }
    const made = sum();
    if (at < tokens.length) fail(`Unexpected "${tokens[at].op ?? tokens[at].id ?? tokens[at].n}".`);
    return made;
  }

  //: A slider's range when the line does not give one: round the value, to three times it on the side it is on.
  function span(value) {
    if (value === 0) return [-5, 5];
    return value > 0 ? [0, value * 3] : [value * 3, 0];
  }
  function niceStep(raw) {
    const mag = 10 ** Math.floor(Math.log10(raw));
    const n = raw / mag;
    return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * mag;
  }

  //: **`parse(source)`**: the fence's lines as `{title, curves: [{label, text, fn, error}], params, x, y, errors}`.
  function parse(source) {
    const out = { title: "", curves: [], params: [], x: null, y: null, errors: [] };
    // One way to split each number (digits with an optional fraction, or a bare fraction), so a long run of
    // digits that fails to match is linear, not quadratic (CodeQL js/polynomial-redos; a note's text is the input).
    const N = "(?:\\d+(?:\\.\\d+)?|\\.\\d+)";
    const num = `(-?${N})`;
    const paramRe = new RegExp(`^([A-Za-z]{1,8})\\s*=\\s*${num}\\s*(?:\\[\\s*${num}\\s*[,;]\\s*${num}\\s*(?:[,;]\\s*(${N})\\s*)?\\])?$`);
    const viewRe = new RegExp(`^([xy])\\s*:\\s*${num}\\s*(?:\\.\\.|,|\\bto\\b)\\s*${num}$`);
    const curveRe = /^(?:y|[A-Za-z]\(x\))\s*=\s*(.+)$/;
    const rest = [];
    for (const raw of String(source).split("\n")) {
      const cut = raw.search(/\s#/);  // linear; a `\s+#.*$` replace is quadratic on a long run of spaces
      const line = (cut >= 0 ? raw.slice(0, cut) : raw).trim();
      if (!line || line.startsWith("#")) continue;
      const title = /^title\s*:\s*(.+)$/i.exec(line);
      const view = viewRe.exec(line);
      const param = paramRe.exec(line);
      if (title) out.title = title[1];
      else if (view) {
        const [lo, hi] = [Number(view[2]), Number(view[3])];
        if (lo < hi) out[view[1]] = [lo, hi];
        else out.errors.push(`${view[1]}: the first number must be the smaller.`);
      } else if (param && !/^(?:y|x|e|pi|tau)$/i.test(param[1]) && !Object.hasOwn(FUNCS, param[1].toLowerCase())) {
        if (out.params.length >= MAX_PARAMS || out.params.some((p) => p.name === param[1])) {
          out.errors.push(out.params.length >= MAX_PARAMS ? `At most ${MAX_PARAMS} sliders.` : `"${param[1]}" is set twice.`);
          continue;
        }
        const value = Number(param[2]);
        let [lo, hi] = param[3] !== undefined ? [Number(param[3]), Number(param[4])] : span(value);
        if (lo > hi) [lo, hi] = [hi, lo];
        lo = Math.min(lo, value);
        hi = Math.max(hi, value);
        out.params.push({ name: param[1], value, min: lo, max: hi, step: Number(param[5]) > 0 ? Number(param[5]) : niceStep((hi - lo || 1) / 100) });
      } else rest.push(line);
    }
    const names = new Set(["x", ...out.params.map((p) => p.name)]);
    for (const line of rest) {
      const given = curveRe.exec(line);
      //: A bare expression with an x in it is a curve too: "sin(x)".
      const text = given ? given[1] : /(?:^|[^a-z])x(?:[^a-z]|$)/i.test(plain(line)) && !line.includes("=") ? line : null;
      if (text === null) {
        out.errors.push(`Not understood: ${line}`);
        continue;
      }
      if (out.curves.length >= MAX_CURVES) {
        out.errors.push(`At most ${MAX_CURVES} curves.`);
        continue;
      }
      const curve = { label: given ? line : `y = ${line}`, text, fn: null, error: "" };
      try {
        curve.fn = compile(text, names);
      } catch (error) {
        curve.error = error.message;
      }
      out.curves.push(curve);
    }
    return out;
  }

  //: Tick values inside [lo, hi], about `target` of them, on 1, 2 or 5 times a power of ten.
  function ticks(lo, hi, target = 8) {
    const step = niceStep((hi - lo) / target);
    const out = [];
    for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + step * 1e-9 && out.length < 60; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : Number(v.toPrecision(12)));
    return { step, values: out };
  }
  function tickText(value, step) {
    const places = Math.min(8, Math.max(0, -Math.floor(Math.log10(step) + 1e-9)));
    const text = value.toFixed(places);
    return /^-0(\.0+)?$/.test(text) ? text.slice(1) : text;
  }

  //: The curve as runs of points `[x, y]`: a run ends at a value that is not a number, far off the picture, or a jump
  //: across the window (the tan curve's asymptote is not a line).
  function runs(fn, vars, x0, x1, y0, y1, count = 600) {
    const out = [];
    let run = [];
    let prev = null;
    const height = y1 - y0;
    for (let i = 0; i <= count; i++) {
      const x = x0 + ((x1 - x0) * i) / count;
      vars.x = x;
      let y;
      try {
        y = fn(vars);
      } catch {
        y = NaN;
      }
      if (!Number.isFinite(y) || Math.abs(y) > 1e9) {
        if (run.length) out.push(run);
        run = [];
        prev = null;
        continue;
      }
      if (prev !== null && Math.abs(y - prev) > height * 4) {
        if (run.length) out.push(run);
        run = [];
      }
      run.push([x, y]);
      prev = y;
    }
    if (run.length) out.push(run);
    return out;
  }

  //: The window when the fence gives none: x -10 to 10; y from the middle 96% of the values, with a margin.
  function autoY(curves, vars, x0, x1) {
    const seen = [];
    for (const curve of curves) {
      if (!curve.fn) continue;
      for (const run of runs(curve.fn, vars, x0, x1, -1e9, 1e9, 200)) for (const [, y] of run) seen.push(y);
    }
    if (!seen.length) return [-5, 5];
    seen.sort((a, b) => a - b);
    const lo = seen[Math.floor((seen.length - 1) * 0.02)];
    const hi = seen[Math.ceil((seen.length - 1) * 0.98)];
    const pad = (hi - lo || 2) * 0.12;
    return [lo - pad, hi + pad];
  }
  // DOC-GRAPH-END

  const PAD = { l: 44, r: 10, t: 10, b: 24 };
  const SVG = "http://www.w3.org/2000/svg";
  const HUES = ["blue", "orange", "green", "violet", "red", "teal"];
  const svgEl = (name, attrs = {}, parent = null) => {
    const el = document.createElementNS(SVG, name);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    parent?.append(el);
    return el;
  };
  const hue = (index) => (typeof CATEGORY_PALETTE === "object" && CATEGORY_PALETTE[HUES[index % HUES.length]]) || "currentColor";

  //: **`fill(figure, source)`**: draws the plot, its sliders and its legend into `figure`. Returns false (and leaves the
  //: reasons in the figure) when no line made a curve, so Read can keep the fence as code.
  function fill(figure, source) {
    const model = parse(source);
    figure.replaceChildren();
    const drawable = model.curves.filter((c) => c.fn);
    const vars = { x: 0 };
    for (const p of model.params) vars[p.name] = p.value;
    const issues = [...model.errors, ...model.curves.filter((c) => c.error).map((c) => `${c.label}: ${c.error}`)];
    const note = (parent) => {
      if (!issues.length) return;
      const list = document.createElement("ul");
      list.className = "dg-issues";
      for (const line of issues) list.append(Object.assign(document.createElement("li"), { textContent: line }));
      parent.append(list);
    };
    if (!drawable.length) {
      const empty = document.createElement("p");
      empty.className = "dg-empty";
      empty.textContent = "Nothing to draw yet. Write a line such as y = sin(x).";
      figure.append(empty);
      note(figure);
      return false;
    }
    const x = model.x || [-10, 10];
    let view = { x0: x[0], x1: x[1], y0: 0, y1: 0 };
    [view.y0, view.y1] = model.y || autoY(drawable, vars, x[0], x[1]);
    const home = { ...view };

    //: The picture is as many units as it has pixels, so its text stays the page's size at any width; `fit` follows the box.
    let W = 640;
    let H = 360;
    const svg = svgEl("svg", { class: "dg-svg", focusable: "false", "aria-hidden": "true" });
    const clipId = `dg-clip-${Math.random().toString(36).slice(2, 8)}`;
    const clip = svgEl("rect", {}, svgEl("clipPath", { id: clipId }, svgEl("defs", {}, svg)));
    const grid = svgEl("g", { class: "dg-grid" }, svg);
    const lines = svgEl("g", { "clip-path": `url(#${clipId})` }, svg);
    const paths = drawable.map((_, i) => svgEl("path", { class: "dg-curve", stroke: hue(i), fill: "none" }, lines));
    const dots = drawable.map((_, i) => svgEl("circle", { class: "dg-dot", r: 4, fill: hue(i), visibility: "hidden" }, lines));
    const frame = svgEl("rect", { class: "dg-frame", fill: "none" }, svg);

    const px = (v) => PAD.l + ((v - view.x0) / (view.x1 - view.x0)) * (W - PAD.l - PAD.r);
    const py = (v) => PAD.t + ((view.y1 - v) / (view.y1 - view.y0)) * (H - PAD.t - PAD.b);
    const unx = (p) => view.x0 + ((p - PAD.l) / (W - PAD.l - PAD.r)) * (view.x1 - view.x0);
    const clampPx = (v) => Math.max(-1e5, Math.min(1e5, v));

    const readout = document.createElement("p");
    readout.className = "dg-readout";
    const paint = () => {
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      for (const box of [clip, frame]) {
        for (const [name, value] of Object.entries({ x: PAD.l, y: PAD.t, width: W - PAD.l - PAD.r, height: H - PAD.t - PAD.b })) box.setAttribute(name, value);
      }
      grid.replaceChildren();
      //: One label per 56 px across and 36 px down, so a narrow column keeps its labels apart.
      const tx = ticks(view.x0, view.x1, Math.max(2, Math.floor((W - PAD.l - PAD.r) / 56)));
      const ty = ticks(view.y0, view.y1, Math.max(2, Math.floor((H - PAD.t - PAD.b) / 36)));
      for (const v of tx.values) {
        const at = px(v);
        svgEl("line", { x1: at, x2: at, y1: PAD.t, y2: H - PAD.b, class: v === 0 ? "dg-axis" : "dg-line" }, grid);
        svgEl("text", { x: at, y: H - PAD.b + 15, "text-anchor": "middle" }, grid).textContent = tickText(v, tx.step);
      }
      for (const v of ty.values) {
        const at = py(v);
        svgEl("line", { x1: PAD.l, x2: W - PAD.r, y1: at, y2: at, class: v === 0 ? "dg-axis" : "dg-line" }, grid);
        svgEl("text", { x: PAD.l - 5, y: at + 4, "text-anchor": "end" }, grid).textContent = tickText(v, ty.step);
      }
      drawable.forEach((curve, i) => {
        const d = runs(curve.fn, vars, view.x0, view.x1, view.y0, view.y1)
          .map((run) => run.map(([a, b], k) => `${k ? "L" : "M"}${px(a).toFixed(1)} ${clampPx(py(b)).toFixed(1)}`).join(""))
          .join("");
        paths[i].setAttribute("d", d);
      });
    };
    const trace = (clientX) => {
      const box = svg.getBoundingClientRect();
      const at = ((clientX - box.left) / box.width) * W;
      if (at < PAD.l || at > W - PAD.r) return;
      const here = unx(at);
      vars.x = here;
      const parts = [`x = ${+here.toFixed(3)}`];
      drawable.forEach((curve, i) => {
        let y = NaN;
        try {
          y = curve.fn(vars);
        } catch {
          y = NaN;
        }
        const shown = Number.isFinite(y) && y >= view.y0 && y <= view.y1;
        dots[i].setAttribute("visibility", shown ? "visible" : "hidden");
        if (shown) {
          dots[i].setAttribute("cx", px(here).toFixed(1));
          dots[i].setAttribute("cy", py(y).toFixed(1));
        }
        parts.push(`${drawable.length > 1 ? `y${i + 1}` : "y"} = ${Number.isFinite(y) ? +y.toFixed(3) : "undefined"}`);
      });
      readout.textContent = parts.join(", ");
    };
    const untrace = () => {
      dots.forEach((dot) => dot.setAttribute("visibility", "hidden"));
      readout.textContent = "";
    };
    //: A move or zoom of the window, by fractions of its own size.
    const pan = (fx, fy) => {
      const [w, h] = [view.x1 - view.x0, view.y1 - view.y0];
      view = { x0: view.x0 + w * fx, x1: view.x1 + w * fx, y0: view.y0 + h * fy, y1: view.y1 + h * fy };
      paint();
    };
    const zoom = (factor, cx = (view.x0 + view.x1) / 2, cy = (view.y0 + view.y1) / 2) => {
      const next = { x0: cx + (view.x0 - cx) * factor, x1: cx + (view.x1 - cx) * factor, y0: cy + (view.y0 - cy) * factor, y1: cy + (view.y1 - cy) * factor };
      if (next.x1 - next.x0 < 1e-6 || next.x1 - next.x0 > 1e7 || next.y1 - next.y0 < 1e-6 || next.y1 - next.y0 > 1e7) return;
      view = next;
      paint();
    };
    const reset = () => {
      view = { ...home };
      paint();
    };

    //: Drag to move the window; the pointer is captured so a drag past the edge still ends.
    let drag = null;
    svg.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      svg.setPointerCapture?.(event.pointerId);
      drag = { x: event.clientX, y: event.clientY };
      untrace();
    });
    svg.addEventListener("pointermove", (event) => {
      if (!drag) return trace(event.clientX);
      const box = svg.getBoundingClientRect();
      const [dx, dy] = [event.clientX - drag.x, event.clientY - drag.y];
      drag = { x: event.clientX, y: event.clientY };
      pan((-dx / box.width) * (W / (W - PAD.l - PAD.r)), (dy / box.height) * (H / (H - PAD.t - PAD.b)));
    });
    for (const type of ["pointerup", "pointercancel"]) svg.addEventListener(type, () => (drag = null));
    svg.addEventListener("pointerleave", untrace);
    //: Ctrl and the wheel (a trackpad pinch is the same event) zooms about the pointer; the wheel alone scrolls the page.
    svg.addEventListener("wheel", (event) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const box = svg.getBoundingClientRect();
      zoom(event.deltaY > 0 ? 1.15 : 1 / 1.15, unx(((event.clientX - box.left) / box.width) * W), view.y1 - ((((event.clientY - box.top) / box.height) * H - PAD.t) / (H - PAD.t - PAD.b)) * (view.y1 - view.y0));
    }, { passive: false });

    const plot = document.createElement("div");
    plot.className = "dg-plot";
    plot.tabIndex = 0;
    plot.setAttribute("role", "group");
    plot.setAttribute("aria-label", `Graph of ${drawable.map((c) => c.label).join("; ")}. Arrow keys move, plus and minus zoom, 0 resets.`);
    plot.addEventListener("keydown", (event) => {
      const arrows = { ArrowLeft: [-0.1, 0], ArrowRight: [0.1, 0], ArrowUp: [0, 0.1], ArrowDown: [0, -0.1] }[event.key];
      if (arrows) pan(...arrows);
      else if (event.key === "+" || event.key === "=") zoom(1 / 1.25);
      else if (event.key === "-" || event.key === "_") zoom(1.25);
      else if (event.key === "0") reset();
      else return;
      event.preventDefault();
      event.stopPropagation();
    });
    plot.append(svg);

    const tools = document.createElement("span");
    tools.className = "dg-tools";
    tools.append(smallButton("ph:plus", "Zoom in", () => zoom(1 / 1.25)), smallButton("ph:minus", "Zoom out", () => zoom(1.25)), smallButton("ph:arrows-in", "Reset the view", reset));
    plot.append(tools);

    const key = document.createElement("ul");
    key.className = "dg-key";
    drawable.forEach((curve, i) => {
      const item = document.createElement("li");
      const swatch = document.createElement("span");
      swatch.className = "dg-swatch";
      swatch.style.background = hue(i);
      item.append(swatch, Object.assign(document.createElement("span"), { textContent: curve.label }));
      key.append(item);
    });
    const head = model.title ? Object.assign(document.createElement("figcaption"), { className: "dg-title", textContent: model.title }) : null;

    const sliders = document.createElement("div");
    sliders.className = "dg-params";
    for (const param of model.params) {
      const row = document.createElement("label");
      row.className = "dg-param";
      row.append(Object.assign(document.createElement("span"), { className: "dg-name", textContent: param.name }));
      //: Not a plain range assignment in code (a frozen lint counts those): the value field upgrades it on first reach (`data-unit` asks for one; value-field.js).
      const slider = document.createElement("input");
      slider.setAttribute("type", "range");
      slider.className = "dg-slider";
      slider.dataset.unit = "";
      slider.setAttribute("aria-label", `${param.name}, a number to try`);
      Object.assign(slider, { min: param.min, max: param.max, step: param.step, value: param.value });
      slider.addEventListener("input", () => {
        vars[param.name] = Number(slider.value);
        paint();
      });
      row.append(slider);
      sliders.append(row);
    }

    paint();
    figure.append(...[head, plot, readout, key, model.params.length ? sliders : null].filter(Boolean));
    note(figure);
    //: A column that is 300 px or 900 px wide gets a picture of that many units, about half as tall, between 220 and 460.
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(() => {
        const wide = Math.round(plot.clientWidth);
        if (wide < 120 || wide === W) return;
        W = wide;
        H = Math.max(220, Math.min(460, Math.round(wide * 0.56)));
        paint();
      }).observe(plot);
    }
    return true;
  }

  Object.assign(docMathRender, { graph: { parse, compile, ticks, runs, fill } });
})();
