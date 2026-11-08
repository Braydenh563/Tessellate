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
  //: The phone keyboard that fits what the field takes: digits for whole numbers from zero up, the decimal key where a
  //: fraction is possible (the parser reads "1.5"), and the full keyboard where a minus is (neither numeric keypad has one).
  const [lo, hi] = [bound("min", NaN), bound("max", NaN)];
  input.inputMode = lo < 0 ? "text" : [lo, hi, opts.step ?? 1].every(Number.isInteger) ? "numeric" : "decimal";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.setAttribute("aria-label", opts.label || "Value");
  input.value = shown;
  //: `size` is the fallback; the stylesheet's `field-sizing: content` fits the text itself (`size` alone drew 63px for "50").
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
  //: Escape has two stages: the first puts a half-typed number back and keeps the focus (a keyboard user is not thrown
  //: to the page), the second hands the focus to its slider (`opts.home`), never the page. True when it reverted.
  input.vfRevert = () => {
    if (input.value.trim() === shown) return false;
    paint();
    input.select();
    return true;
  };
  const leave = () => {
    const home = opts.home?.();
    home?.isConnected ? home.focus() : input.blur();
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
      if (!input.vfRevert()) leave();
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
    const forId = slider.id ? (scan ? scan.outs.get(slider.id) : document.querySelector(`output[for="${CSS.escape(slider.id)}"]`)) : null;
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
    //: Read live: a board's history grows its slider's `max` while the field lives.
    const min = () => Number(slider.min || 0);
    const max = () => Number(slider.max || 100);
    const step = () => (Number(slider.step) > 0 ? Number(slider.step) : 1);
    const unit = source ? source.textContent.trim().replace(/^[-\d.,\s]+/, "") : slider.dataset.unit;
    const host = document.createElement("span");
    host.className = `value-field-range ${source ? source.className : ""}`.trim();
    if (source) source.classList.add("value-field-source");
    (source || slider).after(host);
    //: Named by what the slider is named by (aria-label, else its label words without the readout, else its title), never
    //: by a title's long explanation first.
    const said = source ? source.textContent : "";
    const label = slider.getAttribute("aria-label") || (scan ? scan.labels.get(slider) || [] : [...(slider.labels || [])]).map((l) => l.textContent.replace(said, "").trim()).join(" ").trim() || slider.title || "Value";
    const field = valueField(host, {
      value: Number(slider.value),
      min,
      max,
      step: step(),
      label: `${label}, type a value`,
      home: () => slider,
      //: `data-value-of` says "3 of 12": a scrubber's position means little without its length.
      format: (v) => `${Math.round(v * 100) / 100}${slider.hasAttribute("data-value-of") ? ` of ${max()}` : unit}`,
      onCommit: (v) => {
        const snapped = Math.min(max(), Math.max(min(), min() + Math.round((v - min()) / step()) * step()));
        slider.value = String(snapped);
        slider.dispatchEvent(new Event("input", { bubbles: true }));
        slider.dispatchEvent(new Event("change", { bubbles: true }));
        field.set(Number(slider.value));
      },
    });
    const sync = () => field.set(Number(slider.value));
    slider.addEventListener("input", sync);
    slider.addEventListener("change", sync);
    //: Settled on what the readout says, or the slider where it has none. Also the refresh a surface that writes the
    //: readout or `slider.value` without an event gets (on the next reach, or `valueField.refresh()`).
    slider.vfRefresh = () => {
      const said = source ? valueFieldParse(source.textContent) : null;
      if (said !== null) field.set(said);
      else sync();
    };
    host.vfSlider = slider;
    slider.vfRefresh();
    return field;
  };
  //: **The page's readouts and labels are read once for the scan** (INBOX 1696 f): one `output[for]` query and one
  //: `labels` walk per slider over a 12,000-element page was 64 to 72 ms of the first slider hover at 4x CPU, and a
  //: pointer moving over the Settings nav waited behind it. First match wins, as `querySelector` and `labels` give.
  let scan = { outs: new Map(), labels: new Map() };
  for (const out of document.querySelectorAll("output[for]")) scan.outs.has(out.getAttribute("for")) || scan.outs.set(out.getAttribute("for"), out);
  for (const label of document.querySelectorAll("label")) {
    const control = label.control;
    if (control) scan.labels.set(control, [...(scan.labels.get(control) || []), label]);
  }
  document.querySelectorAll('input[type="range"]').forEach(rangeField);
  scan = null;
  //: Once loaded, it follows the pointer and focus itself (app.js only fetches it on the first reach of a slider, and
  //: the reach that fetched it is replayed here by the document scan above).
  for (const type of ["pointerover", "focusin"]) {
    document.addEventListener(type, ({ target }) => {
      //: A reach of the slider or of its field re-reads the readout the surface wrote.
      const slider = target.vfSlider || target.closest?.(".value-field-range")?.vfSlider || target;
      if (!rangeField(slider)) slider.vfRefresh?.();
    });
  }
  //: At the window, before a menu or a panel that is open around the field takes the same Escape and closes itself.
  window.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape" && event.target.vfRevert?.()) {
        event.preventDefault();
        event.stopPropagation();
      }
    },
    true
  );
  valueField.range = rangeField;
  //: For a surface that writes a readout in code: `valueField.refresh()` re-reads every field under `root`.
  valueField.refresh = (root = document) => root.querySelectorAll("input[data-value-field]").forEach((s) => s.vfRefresh?.());
  window.valueField = valueField;
})();
