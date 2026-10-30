// The extract panel's proposal cards, loaded with the first proposal by
// `openExtractPreview` (chat-attach.js): only an extraction draws them, so
// they stay off the boot scripts' gzip budget (tests/test_static_compression.py).

const EXTRACT_LINK_KIND_LABEL = { sibling: "new note", source: "source", related: "related" };

function extractRefLabel(ref, notes) {
  if (ref.startsWith("existing:")) return "an existing note";
  const note = notes.find((n) => n.ref === ref);
  return note ? note.title || clipText(notePreviewText(note.content), 30) : ref;
}

function renderExtractPreview(body) {
  const status = $("extract-status");
  status.classList.remove("error");
  status.textContent =
    body.message ||
    `${nounCount(body.notes.length, "note")} proposed: review, then save.`;

  // Built with createElement, not an `innerHTML` template per iteration.
  // The old version escaped everything correctly, so this is not a security
  // fix: it is this file's own rule (see the header comment: "All DOM nodes
  // are built with createElement/textContent, never innerHTML"), and the rule
  // exists because an `innerHTML` assignment inside a loop re-invokes the HTML
  // parser once per proposed note, and because the next person to add a field
  // here is one forgotten `escapeHtml` away from an injection.
  const field = (type, className, { placeholder, label, value } = {}) => {
    const input = document.createElement("input");
    input.type = type;
    input.className = className;
    if (placeholder) input.placeholder = placeholder;
    if (label) input.setAttribute("aria-label", label);
    if (value !== undefined) input.value = value;
    return input;
  };

  const list = $("extract-notes-list");
  list.replaceChildren();
  for (const note of body.notes) {
    const card = document.createElement("div");
    card.className = "extract-note-card";
    card.dataset.ref = note.ref;

    const keepLabel = document.createElement("label");
    keepLabel.className = "row align-center checkbox-label";
    const keep = field("checkbox", "extract-note-keep");
    keep.checked = true;
    keepLabel.append(keep, document.createTextNode(" Keep this note"));

    const title = field("text", "extract-note-title", {
      placeholder: "Title (optional)",
      label: "Note title",
      value: note.title || "",
    });

    const content = document.createElement("textarea");
    content.className = "extract-note-content";
    content.rows = 6;
    content.setAttribute("aria-label", "Note content");
    content.value = note.content;

    const meta = document.createElement("div");
    meta.className = "row extract-note-meta";
    const category = document.createElement("span");
    category.className = "muted extract-note-category";
    category.textContent = `Filed under: ${note.category}`;
    meta.append(
      category,
      field("text", "extract-note-tags", {
        placeholder: "Tags, comma separated",
        label: "Tags for this note",
      })
    );

    card.append(keepLabel, title, content, meta);
    list.appendChild(card);
  }

  const linksBox = $("extract-links-list");
  linksBox.replaceChildren();
  if (body.links.length) {
    const heading = document.createElement("p");
    heading.className = "muted";
    heading.textContent = "Links";
    linksBox.appendChild(heading);
  }
  for (const link of body.links) {
    const row = document.createElement("label");
    row.className = "row align-center extract-link-row checkbox-label";
    row.dataset.sourceRef = link.source_ref;
    row.dataset.targetRef = link.target_ref;
    const kindLabel = EXTRACT_LINK_KIND_LABEL[link.kind] || "note";
    // Raw, not escaped: this now goes into a text node, where escaping would
    // render the entities literally ("A &amp; B" on screen).
    const target = link.target_preview || extractRefLabel(link.target_ref, body.notes);
    const keep = document.createElement("input");
    keep.type = "checkbox";
    keep.className = "extract-link-keep";
    keep.checked = true;
    const desc = document.createElement("span");
    desc.className = "extract-link-desc";
    const why = document.createElement("span");
    why.className = "muted";
    why.textContent = `(${kindLabel}: ${link.reason})`;
    desc.append(
      document.createTextNode(
        `${extractRefLabel(link.source_ref, body.notes)} → ${target} `
      ),
      why
    );
    row.append(keep, desc);
    linksBox.appendChild(row);
  }

  $("extract-commit").disabled = body.notes.length === 0;
}
