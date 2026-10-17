// dash-day.js: the dashboard's day digest line, moved out of dashboard.js on 2026-10-12 for the boot gzip budget; `LAZY_ENTRY_POINTS.dashDay` (app.js) stands in, nobody reads its return.

//: **The day, from the engine** (CHAT_PLAN section 2, the dashboard row):
//: what is due, the open questions, what changed since yesterday and the
//: topics gone quiet, from `/insights/day` with no model. Every line is a
//: count or words quoted from one note or reminder, and a quote opens where
//: it came from. The model's week stays below, on request.
async function renderDayDigest(box) {
  let day;
  try {
    day = await apiJson("/insights/day", { silent: true });
  } catch {
    box.replaceChildren();
    return;
  }
  //: The dashboard's own list (`.dash-list`): every line opens where it came
  //: from, a quote its note or the reminders, a count the list it counted.
  const list = document.createElement("ul");
  list.className = "dash-list digest-day-lines";
  const opens = {
    due: () => switchTab("reminders"),
    questions: async () => {
      await switchTab("notes");
      showNotesSection("questions");
    },
    changed: () => switchTab("notes"),
    quiet: async (line) => {
      await switchTab("notes");
      showCategoryNotes(line.category);
    },
  };
  for (const line of day.lines || []) {
    //: **A sentence the composer wrote is a sentence, not a button** (INBOX
    //: 904 B83: "One note written and one note edited since this time
    //: yesterday" took the row's hover and click like a control). It is read,
    //: and the quotes under it are what open; a quiet topic's line links its
    //: category name, the one thing in it there is to open.
    if (line.kind !== "quote") {
      list.appendChild(digestSaidLine(line, opens));
      continue;
    }
    const li = document.createElement("li");
    li.className = line.kind === "quote" ? "digest-day-line muted text-sm" : "digest-day-line";
    li.dataset.kind = line.kind;
    li.dataset.part = line.part;
    const source = line.source || {};
    const open = source.entry_id ? () => flashEntry(source.entry_id) : () => opens[line.part](line);
    //: The link is inside the item: an `li` given `role="link"` stops being a
    //: list item, and axe's `list` rule (serious) fails the `ul` for it. The
    //: whole row still takes the click; the words take the keys.
    const link = document.createElement("span");
    link.setAttribute("role", "link");
    link.tabIndex = 0;
    //: A quote is the note's own words, Markdown and all: plain here (INBOX 820).
    link.textContent = notePreviewText(flattenNoteMarkdown(line.text));
    link.addEventListener("keydown", (event) => {
      if (event.key === "Enter") open();
    });
    li.appendChild(link);
    li.addEventListener("click", open);
    list.appendChild(li);
  }
  if (!list.childElementCount) {
    const quiet = document.createElement("p");
    quiet.className = "muted";
    quiet.textContent = day.empty || "";
    box.replaceChildren(quiet);
    return;
  }
  box.replaceChildren(list);
}

function digestSaidLine(line, opens) {
  const li = document.createElement("li");
  li.className = "digest-day-line digest-day-said";
  li.dataset.kind = line.kind;
  li.dataset.part = line.part;
  const text = String(line.text || "");
  const name = line.part === "quiet" ? String(line.category || "") : "";
  if (!name || !text.startsWith(name)) {
    li.textContent = text;
    return li;
  }
  const link = document.createElement("a");
  link.href = "#";
  link.className = "digest-day-open";
  link.textContent = name;
  link.addEventListener("click", (event) => {
    event.preventDefault();
    opens.quiet(line);
  });
  li.append(link, document.createTextNode(text.slice(name.length)));
  return li;
}

//: **The dashboard's pattern** (INBOX 904 B84, the owner: "What's the meaning
//: or use of them?? Can I view them"): its words read as a sentence
//: ("university came up 4 times since 16 July") and open the notes it
//: counted (its subject, filtered) or Tidy, which lists every pattern whole.
//: Confirm and Not right (CHAT_PLAN decision 60) stay behind one ⋯, so the
//: line stays one line; a confirmed one has neither. Lazy, with the day
//: digest, for the boot gzip budget.
function dashPatternBit(bit, pattern) {
  const link = bit.appendChild(document.createElement("a"));
  link.href = "#";
  link.className = "dash-pattern-open";
  link.textContent = pattern.short;
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const subject = pattern.slots?.subject;
    if (subject) showNotesFilter(subject);
    else openTidySheet();
  });
  if (pattern.confirmed) return;
  const send = (verdict) =>
    insightSend(pattern, verdict)
      .then(() => renderDashSubmessage())
      .catch((error) => toast(error.message, true));
  bit.appendChild(
    kebabMenu(
      INSIGHT_VERDICT_ITEMS.map((item) => ({ label: item.label, title: item.title, run: () => send(item.verdict) })),
      "Is this pattern right?"
    )
  );
}
