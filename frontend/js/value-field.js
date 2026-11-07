// value-field.js: the one typeable number with a quick dropdown (INBOX 1694 b, the owner: zoom percentages and page
// numbers "must be typeable and offer a quick dropdown, in any and all little percentage adjustments like that
// anywhere in the app"). Lazy: `LAZY_MODULES.valueField`, and named by the bundles of the surfaces that draw one
// (the viewer, the diagram view, the Library's boards). DESIGN.md, "A number you read and may type".

//: Text to a number: the first number in it, so "150", "150%" and " 1.5 x" all read. Null where there is none.
(() => {
function valueFieldParse(text) {
  const found = /-?\d+(?:[.,]\d+)?/.exec(String(text ?? ""));
  const n = found ? Number(found[0].replace(",", ".")) : NaN;
  return Number.isFinite(n) ? n : null;
}

//: `valueField(host, {value, min, max, format, parse, presets, onCommit, label, suffixWidth})`: fills `host` with a
//: borderless input that reads as text (`format(value)`, "150%"), selects itself on focus, applies on Enter or blur
//: (clamped to min..max, a value that does not parse is put back) and restores on Escape. `presets` (numbers, or
//: `{label, value}`, or `{label, run}` for a row that is not a number, like Fit) adds a chevron that opens a
//: `kebabMenu`. Returns `{set(value), get(), input}`; `set` is for the surface's own changes and never calls
//: `onCommit`. Keys typed inside stay inside: a viewer's "1" or "0" is a digit here.
function valueField(host, opts = {}) {
  //: A bound may be a function (a page count that changes while the field lives).
  const bound = (key, fallback) => {
    const v = typeof opts[key] === "function" ? opts[key]() : opts[key];
    return Number.isFinite(v) ? v : fallback;
  };
  const format = opts.format || ((v) => String(Math.round(v * 100) / 100));
  const parse = opts.parse || valueFieldParse;
  const clamp = (v) => Math.min(bound("max", Infinity), Math.max(bound("min", -Infinity), v));
  let value = Number.isFinite(opts.value) ? opts.value : 0;
  let shown = format(value);

  const wrap = document.createElement("span");
  wrap.className = "value-field";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "value-field-input";
  input.inputMode = "numeric";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.setAttribute("aria-label", opts.label || "Value");
  input.value = shown;
  const size = () => {
    input.size = Math.max(3, input.value.length + 1);
  };
  size();

  const paint = () => {
    shown = format(value);
    input.value = shown;
    size();
  };
  const commit = () => {
    const typed = input.value.trim();
    if (typed === shown) return;
    const next = parse(typed);
    if (next === null || !Number.isFinite(next)) {
      paint();
      return;
    }
    value = clamp(next);
    paint();
    opts.onCommit?.(value);
  };
  input.addEventListener("input", size);
  input.addEventListener("focus", () => input.select());
  input.addEventListener("blur", commit);
  input.addEventListener("keydown", (event) => {
    //: The surface's own keys (a viewer's arrows and digits, a board's tools) are not for a number being typed.
    event.stopPropagation();
    //: A step (a slider's) makes the arrows nudge the number, Shift ten steps; it applies at once.
    if (opts.step && (event.key === "ArrowUp" || event.key === "ArrowDown")) {
      event.preventDefault();
      const typed = parse(input.value.trim());
      const from = typed === null ? value : typed;
      value = clamp(from + (event.key === "ArrowUp" ? 1 : -1) * opts.step * (event.shiftKey ? 10 : 1));
      paint();
      input.select();
      opts.onCommit?.(value);
    } else if (event.key === "Enter") {
      event.preventDefault();
      commit();
      input.select();
    } else if (event.key === "Escape") {
      event.preventDefault();
      paint();
      input.blur();
    }
  });
  wrap.append(input);

  const presets = (opts.presets || []).map((p) => (typeof p === "number" ? { value: p } : p));
  if (presets.length) {
    const rows = presets.map((p) => ({
      label: p.label || format(p.value),
      run: () => {
        if (p.run) return p.run();
        value = clamp(p.value);
        paint();
        opts.onCommit?.(value);
      },
    }));
    const menu = kebabMenu(rows, `${opts.label || "Value"}: choose`);
    menu.classList.add("value-field-menu");
    const opener = menu.querySelector(":scope > button");
    opener.classList.add("value-field-chevron");
    opener.title = "Choose a value";
    opener.replaceChildren();
    const caret = document.createElement("i");
    caret.className = "ph ph-caret-down";
    caret.setAttribute("aria-hidden", "true");
    opener.append(caret);
    wrap.append(menu);
  }
  host.replaceChildren(wrap);
  return {
    input,
    get: () => value,
    set(next) {
      if (!Number.isFinite(next)) return;
      value = next;
      //: A number being typed is not overwritten by a surface that repaints while it waits.
      if (document.activeElement === input && input.value !== shown) shown = format(value);
      else paint();
    },
  };
}
  //: **A slider's readout becomes a field** (INBOX 1694 c, the owner: "type in values for the thickness slider ...
  //: same with any other sliders"). The readout is found from the slider (`output[for]`, `<id>-value`, `<id>-out`, or
  //: an `output` beside it), kept in the page but hidden as the source the surface already writes, and a field
  //: stands next to it with the readout's own unit ("px", "%"). The field mirrors the readout's text (a surface that
  //: sets the slider without an event still shows true) and, on a commit, snaps to the slider's step, sets
  //: `slider.value` and fires `input` then `change`, so the surface's own handlers run as for a drag.
  const readoutOf = (slider) => {
    const byId = (suffix) => (slider.id ? document.getElementById(slider.id + suffix) : null);
    const forId = slider.id ? document.querySelector(`output[for="${slider.id}"]`) : null;
    const bare = slider.id ? document.getElementById(slider.id.replace(/-slider$/, "") + "-value") : null;
    return forId || byId("-value") || byId("-out") || bare || slider.parentElement?.querySelector(":scope > output") || null;
  };
  const rangeField = (slider) => {
    if (!(slider instanceof HTMLInputElement) || slider.type !== "range" || slider.dataset.valueField) return null;
    let source = readoutOf(slider);
    //: A readout that is itself a field (a number box) or a clock (a time slider's) is left alone.
    if (source && (source instanceof HTMLInputElement || /\d:\d/.test(source.textContent))) return null;
    //: A slider with no readout asks for a field after it with `data-value-field="unit"` (the graph's, the pen's).
    if (!source && slider.dataset.unit === undefined) return null;
    slider.dataset.valueField = "1";
    const min = Number(slider.min || 0);
    const max = Number(slider.max || 100);
    const step = Number(slider.step) > 0 ? Number(slider.step) : 1;
    const unit = source ? source.textContent.trim().replace(/^[-\d.,\s]+/, "") : slider.dataset.unit;
    const host = document.createElement("span");
    host.className = `value-field-range ${source ? source.className : ""}`.trim();
    if (source) source.classList.add("value-field-source");
    (source || slider).after(host);
    const label = slider.getAttribute("aria-label") || slider.title || slider.closest("label")?.textContent.trim() || "Value";
    const field = valueField(host, {
      value: Number(slider.value),
      min,
      max,
      step,
      label: `${label}, type a value`,
      format: (v) => `${Math.round(v * 100) / 100}${unit}`,
      onCommit: (v) => {
        const snapped = Math.min(max, Math.max(min, min + Math.round((v - min) / step) * step));
        slider.value = String(snapped);
        slider.dispatchEvent(new Event("input", { bubbles: true }));
        slider.dispatchEvent(new Event("change", { bubbles: true }));
        field.set(Number(slider.value));
      },
    });
    const sync = () => field.set(Number(slider.value));
    slider.addEventListener("input", sync);
    slider.addEventListener("change", sync);
    //: Settled on what the readout says, or the slider where it has none.
    const first = source ? valueFieldParse(source.textContent) : null;
    if (first !== null) field.set(first);
    else sync();
    return field;
  };
  const rangeFieldsIn = (root) => root.querySelectorAll('input[type="range"]').forEach(rangeField);
  rangeFieldsIn(document);
  //: Once loaded, it follows the pointer and focus itself (app.js only fetches it on the first reach of a slider, and
  //: the reach that fetched it is replayed here by the document scan above).
  for (const type of ["pointerover", "focusin"]) document.addEventListener(type, ({ target }) => rangeField(target));
  valueField.range = rangeField;
  window.valueField = valueField;
})();
