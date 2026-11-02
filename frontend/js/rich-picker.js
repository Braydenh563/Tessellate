// rich-picker.js: the rich picker, one recipe for every list of choices that
// is picked by typing or browsing (DESIGN.md's recipe index, "A list of
// choices picked by typing or browsing").
//
// Taken out of the "/" block menu (editor.js), which the owner singled out
// ("I reallllllyyyy like the design of this popup panel menu for the /
// commands. can we do more similar design styles elsewhere in the app??"),
// rather than drawn again: the markup below is what `editorRenderMenu` and
// `editorRenderPreview` built, and the stylesheet's `.rich-picker-*` rules
// are the ones that were `.editor-menu-*`. Its anatomy:
//
//   - a group header (`.rich-picker-group`), pinned while its rows scroll;
//   - a row (`.rich-picker-row`): a square outlined icon tile, a title over
//     one muted line of what it does, and a keycap on the right holding the
//     way to do it without the picker (the markdown, or the chord);
//   - the highlighted row (`.active`): a soft fill with rounded corners,
//     set by the owner of the list, one row at a time;
//   - a preview pane (`.rich-picker-preview`) beside the list, only where a
//     preview says something: the row's tile and name, its description, a
//     live sample, and the "without the menu" hint.
//
// Every builder here uses createElement and textContent: a row's title can
// be a note's own title, and note text is never parsed as markup. Loaded
// before editor.js; nothing here runs at load.

//: The icon class for a `ph:name` token or a bare name.
function richPickerIconClass(icon) {
  return `ph ph-${String(icon || "ph:dot-outline").replace(/^ph:/, "")}`;
}

//: Split a label the app writes as `ph:icon Words` into its two halves, so a
//: list whose rows were `setLabel` strings can hand the icon to the tile.
function richPickerSplitLabel(label) {
  const text = String(label ?? "");
  const match = /^ph:([\w-]+)\s+/.exec(text);
  return match ? { icon: match[1], text: text.slice(match[0].length) } : { icon: "", text };
}

//: The label with the letters that matched the query marked: contiguous when
//: the query is a substring, the fuzzy letters otherwise (`editorFuzzyMatch`,
//: editor.js, when it is loaded).
function richPickerFillLabel(el, label, query) {
  const text = String(label || "");
  const needle = String(query || "").toLowerCase();
  let hits = [];
  if (needle) {
    const at = text.toLowerCase().indexOf(needle);
    hits = at >= 0
      ? Array.from({ length: needle.length }, (_, i) => at + i)
      : (typeof editorFuzzyMatch === "function" && editorFuzzyMatch(text, needle)) || [];
  }
  if (!hits.length) {
    el.textContent = text;
    return;
  }
  const lit = new Set(hits);
  let run = "";
  let runLit = false;
  const flush = () => {
    if (!run) return;
    if (runLit) {
      const mark = document.createElement("mark");
      mark.className = "rich-picker-hit";
      mark.textContent = run;
      el.appendChild(mark);
    } else {
      el.appendChild(document.createTextNode(run));
    }
    run = "";
  };
  for (let i = 0; i < text.length; i += 1) {
    const on = lit.has(i);
    if (on !== runLit) {
      flush();
      runLit = on;
    }
    run += text[i];
  }
  flush();
}

//: The icon's tile: one size for every row, so the titles line up on one edge
//: and the kinds read by shape before they are read by word. `tint` is a
//: callout kind (its tile wears the block's own ink); `face` is an element
//: to stand in the tile instead of a glyph (Atlas's face on its own row).
function richPickerTile({ icon, tint, face } = {}) {
  const tile = document.createElement("span");
  tile.className = "rich-picker-tile";
  if (tint) tile.classList.add("doc-block-kind", `doc-block-kind-${tint}`);
  tile.setAttribute("aria-hidden", "true");
  if (face) {
    tile.classList.add("rich-picker-tile-face");
    tile.appendChild(face);
  } else {
    const glyph = document.createElement("i");
    glyph.className = richPickerIconClass(icon);
    tile.appendChild(glyph);
  }
  return tile;
}

//: A group's heading. `tag` follows the list it sits in (`li` in a `ul`).
function richPickerGroup(text, { tag = "li", className = "" } = {}) {
  const heading = document.createElement(tag);
  heading.className = `rich-picker-group${className ? ` ${className}` : ""}`;
  heading.setAttribute("role", "presentation");
  heading.textContent = text;
  return heading;
}

//: A row. `keys` is the way to do it without the picker, drawn as a keycap;
//: `query` marks the letters that matched; `className` keeps a list's own
//: hook (its sweeps and its keyboard code find rows by it). The row is an
//: option of a listbox: the list owns `aria-activedescendant`, the row only
//: says whether it is the chosen one. `role: null` with `tag: "button"` is
//: the same row as a plain button, for a dialog whose choices are walked by
//: Tab rather than by arrows (the Library's Create picker).
function richPickerRow({ icon, tint, face, label, about, keys, query, tag = "li", id, className = "", role = "option" }) {
  const row = document.createElement(tag);
  row.className = `rich-picker-row${className ? ` ${className}` : ""}`;
  if (tag === "button") row.type = "button";
  if (role) {
    row.setAttribute("role", role);
    row.setAttribute("aria-selected", "false");
  }
  if (id) row.id = id;
  row.appendChild(richPickerTile({ icon, tint, face }));

  const text = document.createElement("span");
  text.className = "rich-picker-text";
  const title = document.createElement("span");
  title.className = "rich-picker-label";
  richPickerFillLabel(title, label, query);
  text.appendChild(title);
  if (about) {
    const line = document.createElement("span");
    line.className = "rich-picker-about";
    line.textContent = about;
    text.appendChild(line);
  }
  row.appendChild(text);
  //: Said as a phrase (audit 1031 N39): the label and the kind sit in two
  //: spans, and a reader joined them as "Harbor launch plannote".
  if (about) row.setAttribute("aria-label", `${title.textContent}, ${about}`);

  if (keys) {
    const cap = document.createElement("kbd");
    cap.className = "rich-picker-keys";
    cap.textContent = keys;
    row.appendChild(cap);
  }
  return row;
}

//: One row lit, the rest not, and the list told which (for a screen reader).
//: `rows` is the list's options in order; returns the lit row.
function richPickerSetActive(list, rows, index) {
  let lit = null;
  rows.forEach((row, i) => {
    const on = i === index;
    row.classList.toggle("active", on);
    row.setAttribute("aria-selected", String(on));
    if (on) lit = row;
  });
  if (list && lit && lit.id) list.setAttribute("aria-activedescendant", lit.id);
  return lit;
}

//: The preview pane's content, for the row in hand: its tile and name, what
//: it does, a live sample (a node the caller has rendered, inert here), and
//: the way to do it without the picker. `keysLead` and `keysTail` word that
//: last line for the kind of key it is ("Type # to write it without the
//: menu", "Press Ctrl+N to do it from anywhere").
function richPickerPreview(pane, { icon, tint, face, label, about, sample, keys, keysLead = "Type", keysTail = "to write it without the menu." }) {
  pane.replaceChildren();
  const head = document.createElement("p");
  head.className = "rich-picker-preview-head";
  const name = document.createElement("span");
  name.textContent = label;
  head.append(richPickerTile({ icon, tint, face }), name);
  pane.appendChild(head);
  if (about) {
    const line = document.createElement("p");
    line.className = "rich-picker-preview-about";
    line.textContent = about;
    pane.appendChild(line);
  }
  if (sample) {
    sample.classList.add("rich-picker-sample");
    sample.inert = true;
    pane.appendChild(sample);
  }
  if (keys && keysLead) {
    const syntax = document.createElement("p");
    syntax.className = "rich-picker-preview-keys";
    syntax.append(`${keysLead} `);
    const code = document.createElement("code");
    code.textContent = keys;
    syntax.append(code, ` ${keysTail}`);
    pane.appendChild(syntax);
  }
}
