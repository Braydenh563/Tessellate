// documents-props.js: the frontmatter model and the properties panel (split out
// of documents.js, audit 1031 DC13 remainder).
//
// What is here: the model (`docFrontmatter*`, edits as `{from, to, insert}`
// spans, never printed YAML) and the panel drawn from it (`renderDocProperties`,
// the note-type fields, `docInsertProperties`). What stayed in documents.js:
// `docTableApplyEdits` (the one way to apply an edit list, which the model
// calls), `docText`, `docSurface` and the dispatch the panel's fields write
// through.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-code.js is: documents.js and documents-cm.js call in here only from
// inside functions, while its own top level declares and reads nothing from
// either. One closure; what other files call is the `Object.assign` at the foot.
(() => {
  // =============================================================================
  // Frontmatter: the properties panel's model (DOCUMENTS_PLAN Phase 3 item 4)
  // =============================================================================
  //
  // The same promise the table model makes, for the same reason: **nothing here
  // ever prints YAML.** Every operation returns a list of `{from, to, insert}`
  // edits in document coordinates, each one covering the value's own span and
  // nothing else, so a document whose frontmatter was written by hand (or by
  // Obsidian, or by this app's own vault import, which writes `category:` and
  // `tags: [a, b]`) keeps its quoting, its spacing and its key order when one
  // field is edited in the panel. A YAML printer would reformat the whole block
  // on the first keystroke, and a notebook whose files come back rewritten every
  // time somebody edits a tag is a notebook whose diffs are noise.
  //
  // The parse is deliberately small, and small is not the same as sloppy: it
  // understands `---` on line 1, `key: value` lines until the closing `---`, and
  // values that are scalars (quoted or not), inline lists (`[a, b]`) or block
  // lists (`- a` on the lines under the key). Anything it does not understand is
  // left alone rather than guessed at: an unparsed line keeps its bytes and the
  // panel simply offers no field for it, which is the only behaviour that cannot
  // lose someone's text.
  //
  // Bracketed by `DOC-FRONTMATTER-BEGIN` / `DOC-FRONTMATTER-END` so
  // `tests/test_doc_frontmatter.py` can run it in node, away from the browser:
  // pure string work, no DOM and no app globals. It uses `docTableApplyEdits`
  // from the table region, because there is one way to apply a list of edits to
  // a string in this file rather than two.

  // DOC-FRONTMATTER-BEGIN

  //: A fence line: exactly three dashes and nothing but whitespace after them.
  //: Deliberately not `---` anywhere in the document: a horizontal rule mid-text
  //: is the same three characters, and the only thing that makes them a
  //: frontmatter fence is being the document's first line.
  const DOC_FM_FENCE = /^---[ \t]*$/;

  //: A key line. The key is what YAML allows without quoting and what the
  //: editors in the plan's competitor table actually write: letters, digits,
  //: underscores, dashes, dots, and spaces inside but never at the ends.
  const DOC_FM_KEY = /^([A-Za-z0-9_][A-Za-z0-9_.\- ]*?)[ \t]*:(.*)$/;

  //: A block list item under a key: `  - value`.
  const DOC_FM_ITEM = /^([ \t]*)-[ \t]?(.*)$/;

  //: The span of one value inside a line: the whitespace on either side is kept
  //: as `lead`/`tail` rather than trimmed away, because putting it back is what
  //: makes an edit to one value leave every other byte alone. A value that is
  //: quoted keeps its quote, and the text is what is inside it.
  function docFmSpan(raw, from) {
    const lead = (/^[ \t]*/.exec(raw) || [""])[0];
    //: `leadIfEmpty` is the space a *key's* value needs when the key has none
    //: yet (`status:`), and it is empty here because a list item never does: an
    //: item's own span starts where its text starts. The parse sets it on the
    //: one span that is a key's value.
    const span = { from, to: from + raw.length, lead, tail: "", quote: "", text: "", leadIfEmpty: "" };
    if (lead.length === raw.length) return span;
    span.tail = (/[ \t]*$/.exec(raw) || [""])[0];
    const inner = raw.slice(lead.length, raw.length - span.tail.length);
    if (inner.length >= 2 && (inner[0] === '"' || inner[0] === "'") && inner[inner.length - 1] === inner[0]) {
      span.quote = inner[0];
      span.text = inner.slice(1, -1);
    } else {
      span.text = inner;
    }
    return span;
  }

  //: The bytes a span currently holds. The no-op test below compares against
  //: this rather than against the trimmed text, so "set it to what it already
  //: says" is an empty edit list even when the value is padded or quoted.
  function docFmRaw(span) {
    const body = span.quote ? span.quote + span.text + span.quote : span.text;
    return span.lead + body + span.tail;
  }

  //: Which scalars cannot be written bare. The list is short on purpose: these
  //: are the characters that would change what the line *is* rather than what it
  //: says.
  function docFmNeedsQuote(text) {
    if (!text) return false;
    if (/^[ \t]|[ \t]$/.test(text)) return true;
    if (/[:#[\]{},]/.test(text)) return true;
    return /^[-?&*!|>%@`]/.test(text);
  }

  //: Put a value back into a span, quoted exactly as it was quoted before and
  //: newly quoted only when the text would otherwise stop being one scalar.
  //: An empty value after a bare `key:` gets its space back, or the result is
  //: `key:value`, which YAML reads as a key called `key:value`.
  function docFmWrite(span, value) {
    const text = String(value == null ? "" : value).replace(/[\r\n]+/g, " ");
    const quote = span.quote || (docFmNeedsQuote(text) ? '"' : "");
    const body = quote ? quote + text.split(quote).join("") + quote : text;
    //: A value cleared back to nothing takes its padding with it: `status:` is
    //: what an empty property looks like, and `status:   ` with the spaces the
    //: old value sat in is trailing whitespace nobody typed.
    if (!body) return "";
    return (span.lead || span.leadIfEmpty || "") + body + span.tail;
  }

  //: Split an inline list's inside (`a, b, c`) into items, with the span of each
  //: one in document coordinates. A comma inside quotes does not split, which is
  //: the piece of YAML people hit immediately: `tags: ["a, b", c]`.
  function docFmSplitInline(text, base) {
    const items = [];
    let start = 0;
    let quote = "";
    for (let at = 0; at <= text.length; at += 1) {
      const ch = at < text.length ? text[at] : ",";
      if (quote) {
        if (ch === quote) quote = "";
        continue;
      }
      if (ch === '"' || ch === "'") {
        quote = ch;
        continue;
      }
      if (ch !== ",") continue;
      const raw = text.slice(start, at);
      //: The one thing that is not an item: the whole of an empty list. `[]` and
      //: `[  ]` are no items at all, where `[a,]` really is a trailing blank.
      if (raw.trim() || items.length || at < text.length) items.push(docFmSpan(raw, base + start));
      start = at + 1;
    }
    return items;
  }

  //: The frontmatter block at the top of a document, or null. Offsets are the
  //: document's, so every edit below is dispatched without a second coordinate
  //: system, exactly as the table model's are.
  function docFrontmatterParse(text) {
    const source = String(text == null ? "" : text);
    const lines = source.split("\n");
    if (!lines.length || !DOC_FM_FENCE.test(lines[0])) return null;
    const starts = [];
    let at = 0;
    for (const line of lines) {
      starts.push(at);
      at += line.length + 1;
    }
    let close = -1;
    for (let i = 1; i < lines.length; i += 1) {
      if (DOC_FM_FENCE.test(lines[i])) {
        close = i;
        break;
      }
    }
    if (close === -1) return null;

    const entries = [];
    for (let i = 1; i < close; i += 1) {
      const match = DOC_FM_KEY.exec(lines[i]);
      if (!match) continue;
      const key = match[1];
      const rest = match[2];
      const span = docFmSpan(rest, starts[i] + lines[i].length - rest.length);
      span.leadIfEmpty = " ";
      const entry = {
        key,
        line: i,
        from: starts[i],
        to: starts[i] + lines[i].length,
        keyFrom: starts[i],
        keyTo: starts[i] + key.length,
        value: span,
        kind: "scalar",
        listStyle: "",
        items: [],
      };
      if (!span.quote && span.text.startsWith("[") && span.text.endsWith("]")) {
        entry.kind = "list";
        entry.listStyle = "inline";
        entry.open = span.from + span.lead.length + 1;
        entry.close = span.to - span.tail.length - 1;
        entry.items = docFmSplitInline(span.text.slice(1, -1), entry.open);
      } else if (!span.text) {
        //: A block list: the key's own line carries no value and the lines under
        //: it are `- item`. Its own kind rather than an empty scalar, because
        //: `tags:` followed by nothing is a key with no value and `tags:`
        //: followed by `- a` is a list, and the panel draws the two differently.
        const items = [];
        let last = i;
        for (let j = i + 1; j < close; j += 1) {
          const item = DOC_FM_ITEM.exec(lines[j]);
          if (!item) break;
          items.push(docFmSpan(lines[j].slice(item[1].length + 1), starts[j] + item[1].length + 1));
          entry.indent = item[1];
          last = j;
        }
        if (items.length) {
          entry.kind = "list";
          entry.listStyle = "block";
          entry.items = items;
          entry.to = starts[last] + lines[last].length;
          i = last;
        } else {
          entry.kind = "empty";
        }
      }
      entries.push(entry);
    }

    return {
      from: 0,
      to: starts[close] + lines[close].length,
      bodyFrom: starts[1],
      bodyTo: starts[close],
      closeFrom: starts[close],
      closeLine: close,
      entries,
      //: Where the document's prose starts: past the closing fence's newline,
      //: which is what the preview and the outline read.
      textFrom: Math.min(source.length, starts[close] + lines[close].length + 1),
    };
  }

  //: The entry for a key, case-insensitively (`Tags` and `tags` are the same
  //: property to anyone reading the panel), or null.
  function docFrontmatterEntry(fm, key) {
    const wanted = String(key == null ? "" : key).trim().toLowerCase();
    return (fm && fm.entries.find((entry) => entry.key.toLowerCase() === wanted)) || null;
  }

  //: Set a scalar. The span is the value's own, so the key, the colon, the gap
  //: after it and every other line keep their bytes. An empty edit list when the
  //: value already reads that way, which is load-bearing: the panel writes on
  //: every input event and a write that changes nothing must not reach the undo
  //: history.
  function docFrontmatterSetEdits(fm, key, value) {
    const entry = docFrontmatterEntry(fm, key);
    if (!entry) return docFrontmatterAddEdits(fm, key, value);
    const span = entry.value;
    const insert = docFmWrite(span, value);
    if (insert === docFmRaw(span)) return [];
    return [{ from: span.from, to: span.to, insert }];
  }

  //: Set the whole list, item by item. An item that reads the same is not
  //: touched at all, which is what keeps `tags: [ one,two ,three ]` from being
  //: tidied up behind its author's back when the second tag is renamed.
  function docFrontmatterSetListEdits(fm, key, values) {
    const entry = docFrontmatterEntry(fm, key);
    const wanted = (values || []).map((value) => String(value == null ? "" : value).trim()).filter(Boolean);
    if (!entry) return wanted.length ? docFrontmatterAddEdits(fm, key, `[${wanted.join(", ")}]`) : [];
    if (entry.kind !== "list") {
      //: A scalar asked to hold a list becomes an inline list, which is the one
      //: place this model rewrites a whole value: `status: draft` turning into
      //: two statuses has no smaller form than that.
      return docFrontmatterSetEdits(fm, key, `[${wanted.join(", ")}]`);
    }
    const edits = [];
    const items = entry.items;
    const shared = Math.min(items.length, wanted.length);
    for (let i = 0; i < shared; i += 1) {
      const span = items[i];
      const insert = docFmWrite(span, wanted[i]);
      if (insert !== docFmRaw(span)) edits.push({ from: span.from, to: span.to, insert });
    }
    if (wanted.length < items.length) {
      //: Removing items takes the separator that *introduced* each of them: the
      //: comma before it inline, the whole line in a block list. Taking the one
      //: after instead is how a list ends up with a trailing comma.
      const last = items[items.length - 1];
      const from = wanted.length
        ? items[wanted.length - 1].to
        : entry.listStyle === "inline"
          ? entry.open
          : entry.value.to;
      edits.push({ from, to: last.to, insert: "" });
    } else if (wanted.length > items.length) {
      const extra = wanted.slice(items.length);
      if (entry.listStyle === "inline") {
        const at = items.length ? items[items.length - 1].to : entry.open;
        edits.push({ from: at, to: at, insert: (items.length ? ", " : "") + extra.join(", ") });
      } else {
        const indent = entry.indent === undefined ? "  " : entry.indent;
        edits.push({ from: entry.to, to: entry.to, insert: extra.map((text) => `\n${indent}- ${text}`).join("") });
      }
    }
    return edits;
  }

  //: A new key, on its own line immediately above the closing fence, so the
  //: order the author put the others in is untouched.
  function docFrontmatterAddEdits(fm, key, value) {
    if (!fm) return [];
    const name = String(key == null ? "" : key).trim();
    if (!name || docFrontmatterEntry(fm, name)) return [];
    const text = String(value == null ? "" : value).replace(/[\r\n]+/g, " ");
    const body = docFmNeedsQuote(text) && !/^\[.*\]$/.test(text) ? `"${text.split('"').join("")}"` : text;
    return [{ from: fm.closeFrom, to: fm.closeFrom, insert: `${name}:${body ? ` ${body}` : ""}\n` }];
  }

  //: A key and everything under it, including the newline that ended its last
  //: line, so removing the only property leaves `---\n---` rather than a blank
  //: line inside the block.
  function docFrontmatterRemoveEdits(fm, key) {
    const entry = docFrontmatterEntry(fm, key);
    if (!entry) return [];
    return [{ from: entry.from, to: Math.min(entry.to + 1, fm.closeFrom), insert: "" }];
  }

  //: The block itself, for a document that has none. The blank line after it is
  //: part of the insert: `---\n---\n# Title` is a document whose first heading
  //: is glued to its properties in every renderer that is not this one.
  function docFrontmatterCreateEdits(text, key, value) {
    const source = String(text == null ? "" : text);
    if (docFrontmatterParse(source)) return [];
    const name = String(key == null ? "" : key).trim() || "tags";
    const body = String(value == null ? "" : value);
    return [{ from: 0, to: 0, insert: `---\n${name}:${body ? ` ${body}` : ""}\n---\n${source.trim() ? "\n" : ""}` }];
  }

  //: The document without its properties, for anything that reads the prose
  //: rather than the file: the preview, the outline, the reading time. Returns
  //: the text unchanged when there is no frontmatter, which is most documents.
  function docFrontmatterStrip(text) {
    const fm = docFrontmatterParse(text);
    if (!fm) return String(text == null ? "" : text);
    return String(text).slice(fm.textFrom).replace(/^\n+/, "");
  }

  //: A document that says `type: Meeting` is of a note type (GRAPH_PLAN KG4), and
  //: the type's fields it has not written yet are the rows the panel offers
  //: empty. `types` is `GET /note-types` (`[{name, fields: [{name, kind}]}]`),
  //: `null` until it has loaded. Pure, so it runs in node: the type is read from
  //: a scalar `type` only (a list or an empty one names nothing), matched the way
  //: the server matches it (case-insensitively), and a field already written is
  //: skipped by the model's own case-blind key lookup.
  function docFrontmatterTypeFields(fm, types) {
    const none = { type: null, fields: [] };
    const entry = fm && docFrontmatterEntry(fm, "type");
    if (!entry || entry.kind !== "scalar" || !Array.isArray(types)) return none;
    const wanted = String(entry.value.text || "").trim().toLowerCase();
    const row = wanted && types.find((t) => t && String(t.name || "").toLowerCase() === wanted);
    if (!row) return none;
    const fields = (row.fields || []).filter((f) => f && f.name && !docFrontmatterEntry(fm, f.name));
    return { type: row.name, fields };
  }

  //: **A document's icon and cover** (DOCUMENTS_PLAN gap row 8, Notion's page
  //: cover and icon). Two ordinary properties, so the file stays plain text any
  //: other editor reads: `icon` is an emoji or `ph:name` (a Phosphor icon, from
  //: the one picker), `cover` is the name of one of the category palette's
  //: colours (`red` ... `pink`, notes-list.js). Anything else in either key is
  //: left alone and not drawn, rather than guessed at.
  function docCoverLook(fm) {
    const text = (key) => {
      const entry = docFrontmatterEntry(fm, key);
      return entry && entry.kind !== "list" ? String(entry.value.text || "").trim() : "";
    };
    const icon = text("icon");
    const cover = text("cover").toLowerCase();
    const named = /^ph:[a-z0-9-]{1,40}$/.test(icon);
    return {
      icon: named ? { kind: "icon", value: icon.slice(3) } : icon && icon.length <= 16 && !/\s/.test(icon) ? { kind: "emoji", value: icon } : null,
      cover: /^[a-z][a-z-]{1,15}$/.test(cover) ? cover : null,
    };
  }

  //: Set one of the two keys, or clear it with `null`, as the smallest edits
  //: (an empty list when it already reads that way).
  function docCoverEdits(fm, key, value) {
    return value == null ? docFrontmatterRemoveEdits(fm, key) : docFrontmatterSetEdits(fm, key, value);
  }

  // DOC-FRONTMATTER-END

  // -----------------------------------------------------------------------------
  // The properties panel: the model above, as fields
  // -----------------------------------------------------------------------------
  //
  // **Why this is DOM outside the editor rather than a widget inside it.** A
  // `Decoration.replace` from a view plugin may not contain a line break:
  // CodeMirror throws "Decorations that replace line breaks may not be specified
  // via plugin" and the whole view stops updating. Frontmatter is three lines at
  // the very least, so the panel cannot be a block widget over it. It is built
  // here and inserted as the first child of `#doc-editor`, which is a flex
  // column, so it sits above the view and shares its column. (Not as a sibling
  // *before* `#doc-editor`: `.doc-source-wrap` is a flex **row**, because the
  // line-number gutter sits beside the text, so a sibling there would be a
  // column to the left of the writing rather than a panel above it.)
  //
  // The frontmatter lines themselves hide in Live the way a table's delimiter
  // row does: one `Decoration.line` per line with `height: 0` plus a per-line
  // `hide()`, and each of those replacements is inside a single line, which is
  // what makes them legal from a plugin.
  //
  // **Writes happen on `change`, not on `input`**, and that is a decision rather
  // than an oversight: `input` would put one transaction per keystroke into the
  // undo history, so Ctrl+Z would take back a letter of a tag at a time, and it
  // would re-enter this function mid-typing on every one of them. `change`
  // fires on Enter and on blur, which is one undo step per edited value: the
  // same granularity the table commands chose for the same reason.
  //
  // **Live only.** Source shows the YAML itself, so a panel there would be two
  // editable copies of one thing on screen at once; Read renders the properties
  // as a block through the preview (`renderDocPreview`). The panel is markdown
  // only, because a `.py` file whose first line is `---` is not a document with
  // properties.

  //: One list of edits, one transaction, through the editor's own dispatch: the
  //: caret, the undo step and the fallback textarea are all handled there.
  function docPropsDispatch(edits) {
    if (!edits || !edits.length) return false;
    return docTableDispatch({ surface: docSurface(), text: docText() }, edits);
  }

  //: The frontmatter as it is *now*. Every write re-parses rather than closing
  //: over the parse the row was built from: between building a row and blurring
  //: its field the document may have been typed in, and an edit dispatched at
  //: stale offsets lands in the middle of somebody's sentence.
  function docPropsNow() {
    return docFrontmatterParse(docText());
  }

  function docPropsShowing() {
    return docView === "live" && docFileType().previewable;
  }

  //: The panel's host, made once and kept. No id: `tests/test_frontend_ids.py`
  //: pairs every `$("...")` in the scripts with an element in index.html, and
  //: index.html cannot hold this one (it is another agent's file, and an empty
  //: host for a panel that only some documents have is markup that lies).
  function docPropsHost(create = false) {
    const editor = $("doc-editor");
    if (!editor) return null;
    let host = editor.querySelector(".doc-props");
    if (!host && create) {
      host = document.createElement("div");
      host.className = "doc-props";
      host.setAttribute("role", "group");
      host.setAttribute("aria-label", "Document properties");
      editor.insertBefore(host, editor.firstChild);
    }
    return host;
  }

  //: What the panel was last drawn from, so typing in the document does not
  //: rebuild a panel that already says the right thing. The whole block's text,
  //: not a hash of it: it is a few dozen characters and comparing it is exact.
  let docPropsDrawn = null;

  //: A row's remove button, and the panel's own small buttons, all from the
  //: app's icon-only ghost recipe rather than from three hand-rolled ones.
  function docPropsIconButton(icon, label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small icon-only doc-prop-btn";
    button.title = label;
    button.setAttribute("aria-label", label);
    const glyph = document.createElement("i");
    glyph.className = `ph ph-${icon}`;
    glyph.setAttribute("aria-hidden", "true");
    button.appendChild(glyph);
    return button;
  }

  //: One value of a list property. A chip is a fact (DESIGN.md's recipe index
  //: says so), and the button beside it inside the chip is the action: removing
  //: this value. The pair is what every tag field in this app already looks
  //: like.
  function docPropsChip(key, value) {
    const box = document.createElement("span");
    box.className = "chip doc-prop-chip";
    const label = document.createElement("span");
    label.textContent = value;
    const remove = docPropsIconButton("x", `Remove ${value}`);
    remove.addEventListener("click", () => {
      const fm = docPropsNow();
      const entry = fm && docFrontmatterEntry(fm, key);
      if (!entry) return;
      const values = entry.items.map((item) => item.text).filter((text) => text !== value);
      docPropsDispatch(docFrontmatterSetListEdits(fm, key, values));
      renderDocProperties(true);
    });
    box.append(label, remove);
    return box;
  }

  //: The field that adds a value to a list. Enter commits, and the panel is
  //: rebuilt with the focus back in this same field, because adding three tags
  //: in a row is one gesture and having to click back into the box between them
  //: is not.
  function docPropsAdder(key) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "doc-prop-add";
    input.placeholder = "Add";
    input.setAttribute("aria-label", `Add a value to ${key}`);
    const commit = () => {
      const value = input.value.trim();
      if (!value) return;
      const fm = docPropsNow();
      const entry = fm && docFrontmatterEntry(fm, key);
      if (!entry) return;
      input.value = "";
      docPropsDispatch(docFrontmatterSetListEdits(fm, key, [...entry.items.map((item) => item.text), value]));
      renderDocProperties(true);
      const again = docPropsHost();
      const field = again && again.querySelector(`[data-doc-prop-add="${CSS.escape(key)}"]`);
      if (field) field.focus();
    };
    input.dataset.docPropAdd = key;
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      commit();
    });
    input.addEventListener("change", commit);
    return input;
  }

  //: A scalar's field. `change` rather than `input`, for the reason at the top
  //: of this section.
  function docPropsField(key, value) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "doc-prop-input";
    input.value = value;
    input.setAttribute("aria-label", key);
    input.addEventListener("change", () => {
      const fm = docPropsNow();
      if (!fm) return;
      docPropsDispatch(docFrontmatterSetEdits(fm, key, input.value));
    });
    return input;
  }

  //: The note types, for the rows a `type:` offers. Loaded once, the first time a
  //: document with a `type` is drawn (a document with none never asks), and
  //: again on the next draw if the request failed. `null` is "not loaded", which
  //: `docFrontmatterTypeFields` reads as no fields.
  let docNoteTypes = null;
  let docNoteTypesAsked = false;
  function docLoadNoteTypes() {
    if (docNoteTypes || docNoteTypesAsked) return;
    docNoteTypesAsked = true;
    apiJson("/note-types")
      .then((types) => {
        docNoteTypes = Array.isArray(types) ? types : [];
        docPropsDrawn = null;
        renderDocProperties();
      })
      .catch(() => {
        docNoteTypesAsked = false;
      });
  }

  //: The type's fields the document has not written: one empty row each, with
  //: the control its kind needs (the note's own Properties sheet draws the same
  //: kinds, note-properties.js). Nothing is written until a value is: a row left
  //: empty adds no line to the file. A value goes in through the model's own add,
  //: so the other lines keep their bytes, and the redraw turns the row into an
  //: ordinary one.
  function docPropsTypeRows(host, fm) {
    if (!docFrontmatterEntry(fm, "type")) return;
    if (!docNoteTypes) {
      docLoadNoteTypes();
      return;
    }
    const { type, fields } = docFrontmatterTypeFields(fm, docNoteTypes);
    for (const field of fields) {
      const row = document.createElement("div");
      row.className = "doc-prop-row doc-prop-unset";
      const key = document.createElement("span");
      key.className = "doc-prop-key";
      key.textContent = field.name;
      key.title = `A field of the ${type} type, not written in this document yet`;
      const value = document.createElement("div");
      value.className = "doc-prop-value";
      const kind = field.kind;
      const input = document.createElement("input");
      input.type = kind === "checkbox" ? "checkbox" : kind === "number" ? "number" : kind === "date" ? "date" : "text";
      input.className = kind === "list" ? "doc-prop-add" : kind === "checkbox" ? "doc-prop-check" : "doc-prop-input";
      if (kind === "list") input.placeholder = "a, b, c";
      input.setAttribute("aria-label", `${field.name} (${type})`);
      input.addEventListener("change", () => {
        const now = docPropsNow();
        if (!now) return;
        let written = "";
        if (kind === "checkbox") written = input.checked ? "true" : "";
        else if (kind === "list") {
          const items = input.value.split(",").map((x) => x.trim()).filter(Boolean);
          written = items.length ? `[${items.join(", ")}]` : "";
        } else if (kind === "note") written = input.value.trim() ? `[[${input.value.trim()}]]` : "";
        else written = input.value.trim();
        if (!written) return;
        docPropsDispatch(docFrontmatterAddEdits(now, field.name, written));
        renderDocProperties(true);
      });
      value.appendChild(input);
      //: KG4: a note field searches the notebook (selection.js); choosing one
      //: fires the box's change, which writes the `[[link]]` above.
      if (kind === "note") {
        value.appendChild(noteFieldPickButton(input));
      }
      //: The written rows end in a trash button; an unwritten one holds its
      //: place, so the fields line up down the panel.
      const spacer = docPropsIconButton("trash", "");
      spacer.classList.add("doc-prop-spacer");
      spacer.removeAttribute("aria-label");
      spacer.removeAttribute("title");
      row.append(key, value, spacer);
      host.appendChild(row);
    }
  }

  //: "Add property": a button that becomes the field for the new key's name, so
  //: the panel never carries an empty row waiting to be filled in and there is
  //: no dialog for something that is one word long.
  function docPropsAddRow(host) {
    const row = document.createElement("div");
    row.className = "doc-prop-new";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small doc-prop-new-btn";
    button.textContent = "Add property";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "doc-prop-input doc-prop-new-input hidden";
    input.placeholder = "Property name";
    input.setAttribute("aria-label", "New property name");
    button.addEventListener("click", () => {
      button.classList.add("hidden");
      input.classList.remove("hidden");
      input.focus();
    });
    const commit = () => {
      const name = input.value.trim();
      input.value = "";
      input.classList.add("hidden");
      button.classList.remove("hidden");
      if (!name) return;
      const fm = docPropsNow();
      if (!fm) return;
      docPropsDispatch(docFrontmatterAddEdits(fm, name, ""));
      renderDocProperties(true);
    };
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        commit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        input.value = "";
        commit();
      }
    });
    input.addEventListener("blur", commit);
    row.append(button, input);
    host.appendChild(row);
  }

  //: The icon and cover row, at the head of the panel: the cover as a band in
  //: the chosen colour with the icon on it, and the buttons that set them.
  //: The colour row is the app's one swatch picker (`swatchPicker`), opened
  //: and closed by the Cover button; the icon comes from the one icon and
  //: emoji picker. Every write is one edit through `docPropsDispatch`, so each
  //: is one Undo step in the document.
  function docPropsLookRow(host, fm) {
    const look = docCoverLook(fm);
    const colour = look.cover && Object.hasOwn(CATEGORY_PALETTE, look.cover) ? CATEGORY_PALETTE[look.cover] : null;
    const row = document.createElement("div");
    row.className = "doc-look";
    const write = (key, value) => {
      const now = docPropsNow();
      if (!now) return;
      docPropsDispatch(docCoverEdits(now, key, value));
      renderDocProperties(true);
    };
    if (colour || look.icon) {
      const band = document.createElement("div");
      band.className = colour ? "doc-cover" : "doc-cover doc-cover-none";
      if (colour) band.style.setProperty("--swatch", colour);
      if (look.icon) {
        const mark = document.createElement("span");
        mark.className = "doc-cover-icon";
        mark.setAttribute("role", "img");
        mark.setAttribute("aria-label", "Document icon");
        if (look.icon.kind === "emoji") mark.textContent = look.icon.value;
        else {
          const glyph = document.createElement("i");
          glyph.className = `ph ph-${look.icon.value}`;
          mark.append(glyph);
        }
        band.append(mark);
      }
      row.append(band);
    }
    const bar = document.createElement("div");
    bar.className = "doc-look-bar";
    const button = (text, run) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ghost small";
      b.textContent = text;
      b.addEventListener("click", run);
      bar.append(b);
      return b;
    };
    const iconButton = button(look.icon ? "Change icon" : "Add icon", () => {
      pickIconOrEmoji({
        anchor: iconButton,
        title: "Document icon",
        onPick: ({ kind, value }) => write("icon", kind === "icon" ? `ph:${value}` : value),
      });
    });
    if (look.icon) button("Remove icon", () => write("icon", null));
    const coverButton = button(look.cover ? "Change cover" : "Add cover", async () => {
      const open = row.querySelector(".doc-look-colours");
      if (open) {
        open.remove();
        return;
      }
      await ensureModule("categories");
      const holder = document.createElement("div");
      holder.className = "doc-look-colours";
      holder.append(swatchPicker({
        label: "Cover colour",
        value: look.cover,
        none: "No cover",
        onChange: () => {},
        onChoose: (key) => write("cover", key),
      }));
      row.append(holder);
    });
    coverButton.setAttribute("aria-haspopup", "true");
    row.prepend(bar);
    host.append(row);
  }

  //: Draw the panel from the document. Called on every document change, so it
  //: does as little as it can: if the frontmatter's own text has not moved, the
  //: panel already says the right thing and nothing is rebuilt.
  //:
  //: `force` is for the panel's own writes (a chip removed, a value added),
  //: which change the text the panel is drawn from and therefore have to redraw
  //: it; everything else must not, because a rebuild while a field has the
  //: focus would take the caret out of it mid-word.
  function renderDocProperties(force = false) {
    const editor = $("doc-editor");
    if (!editor) return;
    const fm = docPropsShowing() ? docFrontmatterParse(docText()) : null;
    const host = docPropsHost(Boolean(fm));
    if (!host) return;
    if (!fm) {
      host.replaceChildren();
      host.classList.add("hidden");
      docPropsDrawn = null;
      return;
    }
    host.classList.remove("hidden");
    const drawn = docText().slice(fm.from, fm.to);
    const holdsFocus = host.contains(document.activeElement);
    if (drawn === docPropsDrawn && host.childElementCount) return;
    docPropsDrawn = drawn;
    if (holdsFocus && !force) return;

    host.replaceChildren();
    docPropsLookRow(host, fm);
    for (const entry of fm.entries) {
      //: The look row owns these two keys: a second, plain text field for each would be two ways to say one thing.
      if (entry.key === "icon" || entry.key === "cover") continue;
      const row = document.createElement("div");
      row.className = "doc-prop-row";
      const key = document.createElement("span");
      key.className = "doc-prop-key";
      key.textContent = entry.key;
      key.title = `The ${entry.key} property, written in this document's frontmatter`;
      const value = document.createElement("div");
      value.className = "doc-prop-value";
      if (entry.kind === "list") {
        for (const item of entry.items) value.appendChild(docPropsChip(entry.key, item.text));
        value.appendChild(docPropsAdder(entry.key));
      } else {
        value.appendChild(docPropsField(entry.key, entry.value.text));
      }
      const remove = docPropsIconButton("trash", `Remove the ${entry.key} property`);
      remove.addEventListener("click", () => {
        const now = docPropsNow();
        if (!now) return;
        docPropsDispatch(docFrontmatterRemoveEdits(now, entry.key));
        renderDocProperties(true);
      });
      row.append(key, value, remove);
      host.appendChild(row);
    }
    docPropsTypeRows(host, fm);
    docPropsAddRow(host);
  }

  //: The "/" menu's and the toolbar's way in, for a document that has no
  //: properties yet. One property (`tags`), because an empty block is a thing
  //: to delete rather than a thing to fill in, and the panel's own "Add
  //: property" covers the rest.
  function docInsertProperties() {
    const text = docText();
    const fm = docFrontmatterParse(text);
    if (fm) {
      //: Already has them: put the caret in the block rather than adding a
      //: second one, which is what a person pressing this twice means.
      docSurface()?.setSelectionRange(fm.bodyFrom, fm.bodyFrom);
      docSurface()?.focus();
      renderDocProperties(true);
      return;
    }
    docPropsDispatch(docFrontmatterCreateEdits(text, "tags", "[]"));
    renderDocProperties(true);
    const host = docPropsHost();
    const field = host && host.querySelector(".doc-prop-add");
    if (field) field.focus();
  }


  //: The file's whole surface: what documents.js and the other files call.
  Object.assign(window, { docFrontmatterParse, docFrontmatterStrip, renderDocProperties, docInsertProperties });
})();
