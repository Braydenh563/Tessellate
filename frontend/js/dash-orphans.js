// dash-orphans.js: the dashboard's Loose ends widget, moved out of dashboard.js on 2026-10-12 for the boot gzip budget. `LAZY_ENTRY_POINTS.dashOrphans` (app.js) stands in for its render.

(() => {
  async function renderOrphanNotesWidget(body) {
    const [entries, graph] = await Promise.all([
      dashEntries(),
      fetchDashGraph().catch(() => null),
    ]);
    // The same degree map `renderMostLinkedWidget` builds, read for its zeroes
    // instead of its peaks.
    const linked = new Set();
    for (const edge of graph?.edges || []) {
      if (typeof edge.source === "number") linked.add(edge.source);
      if (typeof edge.target === "number") linked.add(edge.target);
    }
    // A board is a note by construction here, and an empty canvas is not a
    // stranded thought. Drafts have not been filed yet by definition.
    const real = entries.filter((e) => !e.is_board && !e.is_draft && !e.map_topic);
    // **Category is deliberately not part of this test, and that is a measured
    // decision rather than an oversight.** The first cut of this widget counted
    // a note as stranded only if it had no links, no tags *and* no category, 
    // and it could never fire, because this app files every note as it is
    // saved: on a real 116-note notebook, 116 had a category. A field the app
    // fills in for you says nothing about whether *you* connected anything.
    //
    // Tags and links are the two a person actually chooses, so those are the
    // test. On that same notebook 99 of 116 notes qualified, which is why this
    // is not the list of them it started as. A widget that lists 85% of your
    // notes has told you nothing and made you scroll; the number *is* the
    // finding, so the number leads, and only a handful of oldest offenders come
    // with it as somewhere to actually start.
    const loose = real.filter((entry) => !linked.has(entry.id) && !(entry.tags || []).length);
    if (!real.length) {
      dashEmpty(body, "Write a few notes and this will show how well connected they are.", { label: "ph:plus New note", run: "capture" });
      return;
    }
    const connected = real.length - loose.length;
    const pct = Math.round((connected / real.length) * 100);

    const summary = document.createElement("p");
    summary.className = "dash-loose-summary";
    summary.textContent = loose.length
      ? `${loose.length} of ${real.length} notes have no link and no tag.`
      : `All ${real.length} notes have a link or a tag.`;
    body.appendChild(summary);

    // A meter, not a decorative bar: it carries its own value for a screen
    // reader, which a styled div cannot.
    const meter = document.createElement("div");
    meter.className = "dash-loose-meter";
    meter.setAttribute("role", "meter");
    meter.setAttribute("aria-valuemin", "0");
    meter.setAttribute("aria-valuemax", "100");
    meter.setAttribute("aria-valuenow", String(pct));
    meter.setAttribute("aria-label", `${pct}% of notes are connected`);
    const fill = document.createElement("div");
    fill.className = "dash-loose-fill";
    // A width has to be a real number here, and CSP forbids a `style`
    // attribute: a custom property set through the CSSOM is neither.
    fill.style.setProperty("--dash-loose-pct", `${pct}%`);
    meter.appendChild(fill);
    body.appendChild(meter);

    const caption = document.createElement("p");
    caption.className = "muted dash-loose-caption";
    caption.textContent = `${pct}% connected`;
    body.appendChild(caption);

    if (!loose.length) return;

    // **The widget that names the problem offers the thing that fixes it.**
    // The auto-linker lives as "Suggest links" in the Graph tab's toolbar,
    // among the graph's own display options, so the one screen that tells you
    // most of your notebook is unconnected had no way to act on it, and the
    // feature that would has to be found first. It opens the suggestions inbox
    // (suggestions-inbox.js, KG9) where it stands.
    const connect = document.createElement("button");
    connect.type = "button";
    connect.className = "ghost small dash-loose-action";
    const connectIcon = document.createElement("i");
    connectIcon.className = "ph ph-link ph-lead";
    connectIcon.setAttribute("aria-hidden", "true");
    connect.append(connectIcon, "Find links to add");
    connect.title = "Look for notes worth connecting, and approve them one by one";
    connect.addEventListener("click", () => openSuggestionsInbox("links"));
    //: And the other half of "no link and no tag" (INBOX 162): the filtered
    //: Notes list, where every card carries its own "No tags yet" chip.
    const tagIt = document.createElement("button");
    tagIt.type = "button";
    tagIt.className = "ghost small dash-loose-action";
    const tagIcon = document.createElement("i");
    tagIcon.className = "ph ph-tag ph-lead";
    tagIcon.setAttribute("aria-hidden", "true");
    tagIt.append(tagIcon, "Show untagged notes");
    tagIt.title = "The Notes list, filtered to notes with no tags";
    tagIt.addEventListener("click", () => showNotesFilter("is:untagged"));
    const actions = document.createElement("div");
    actions.className = "row dash-loose-actions";
    actions.append(connect, tagIt);
    body.appendChild(actions);
    // Oldest first: a note written this morning has not had a chance to be
    // filed yet, and nagging about it is how a hygiene widget becomes noise.
    const oldest = [...loose].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    miniEntryList(body, oldest.slice(0, 3), "");
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { renderOrphanNotesWidget });
})();
