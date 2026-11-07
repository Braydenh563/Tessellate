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
    if (event.key === "Enter") {
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
  window.valueField = valueField;
})();
