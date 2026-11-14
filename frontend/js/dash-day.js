// dash-day.js: the dashboard's day digest line, moved out of dashboard.js on 2026-10-12 for the boot gzip budget; `LAZY_ENTRY_POINTS.dashDay` (app.js) stands in, nobody reads its return.

//: **The day, from the engine** (CHAT_PLAN section 2, the dashboard row):
//: what is due, the open questions, what changed since yesterday and the
//: topics gone quiet, from `/insights/day` with no model. Every line is a
//: count or words quoted from one note or reminder, and a quote opens where
//: it came from. The model's week stays below, on request.
(() => {
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
    //: Every counted phrase opens the list it counted (B23: "every number links
    //: to its list"); the sentence around it stays text (INBOX 904 B83), so the
    //: link is the words that hold the number, never the row.
    const spans = [];
    for (const phrase of line.links || []) {
      const at = text.toLowerCase().indexOf(String(phrase).toLowerCase());
      if (at !== -1 && !spans.some((s) => at < s.end && at + phrase.length > s.at)) spans.push({ at, end: at + phrase.length });
    }
    spans.sort((a, b) => a.at - b.at);
    if (!spans.length) {
      li.textContent = text;
      return li;
    }
    let from = 0;
    for (const { at, end } of spans) {
      li.appendChild(document.createTextNode(text.slice(from, at)));
      const link = document.createElement("a");
      link.href = "#";
      link.className = "digest-day-open";
      link.textContent = text.slice(at, end);
      link.addEventListener("click", (event) => {
        event.preventDefault();
        opens[line.part](line);
      });
      li.appendChild(link);
      from = end;
    }
    li.appendChild(document.createTextNode(text.slice(from)));
    return li;
  }

  //: **The dashboard's pattern** (INBOX 904 B84, the owner: "What's the meaning
  //: or use of them?? Can I view them"): its words read as a sentence
  //: ("university came up 4 times since 16 July") and open the notes it
  //: counted (its subject, filtered) or Tidy, which lists every pattern whole.
  //: Confirm and Not right (CHAT_PLAN decision 60) stay behind one ⋯, so the
  //: line stays one line; a confirmed one has its Edit, Not right and Remove
  //: there instead (B9). Lazy, with the day
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
    const send = (verdict) =>
      insightSend(pattern, verdict)
        .then(() => renderDashSubmessage())
        .catch((error) => toast(error.message, true));
    const items = insightVerdictItems(pattern).map((item) => ({ label: item.label, title: item.title, run: () => send(item.verdict) }));
    if (!pattern.confirmed_id) {
      if (items.length) bit.appendChild(kebabMenu(items, "Is this pattern right?"));
      return;
    }
    //: A confirmed one carries Edit, Not right and Remove (B9) where its pair was.
    //: A failed load (false) keeps the pair's own items.
    lazyScript("/js/confirmed-patterns.js").then((ready) => {
      const all = [...items, ...(ready ? confirmedPatternItems(pattern) : [])];
      if (all.length) bit.appendChild(kebabMenu(all, "Manage this pattern"));
    });
  }

  //: The composed line under the greeting (`/insights/today-line`,
  //: `composer_voice.today_line`; INBOX 1300): `seed` is the draw the caller
  //: is in, so the same draw is the same words. Empty when the notebook is.
  async function dashTodayLine(seed) {
    const got = await apiJson(`/insights/today-line?seed=${encodeURIComponent(seed)}`, { silent: true });
    return got?.text || "";
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { dashPatternBit, dashTodayLine, renderDayDigest });
})();
