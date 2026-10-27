// meetings.js: meeting notes (INBOX 644). Loaded on first use by
// `LAZY_MODULES.meetings` (app.js), whose stand-ins for `openNewMeeting` and
// `openMeetingSheet` fetch this file and call the real one: nothing here is
// needed until someone starts or opens a meeting.
//
// The owner: "Can you also redesign and expand and improve the meeting notes
// feature?? I feel like it is neglected and a bit left behind and tucked
// away." The audit (docs/roadmap/agent-remaining/meetings-644.md) found the
// one-click home entry opened a recorder, not a meeting, and four meeting
// shapes that disagreed. A meeting is now one thing: an ordinary note in one
// shape (`entry/meetings.py`), started from New meeting wherever things are
// started, and worked from one sheet: its action items (each one a reminder
// on demand), its decisions, Summarise with the words each line came from,
// and Record into it. Everything but Summarise works with no model.

//: The datetime field's value for "now", to the nearest five minutes: a
//: meeting starts at 14:00, not at 14:03:27.
function meetingNowValue(at = new Date()) {
  const d = new Date(at.getTime());
  d.setSeconds(0, 0);
  d.setMinutes(Math.round(d.getMinutes() / 5) * 5);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

//: "2026-10-07 14:00" (the note's own `date:`, a wall clock with no zone) as
//: words: "Wed 7 Oct, 14:00". A date alone has no time; anything that does
//: not read as a date is shown as written.
function meetingWhenText(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?$/.exec(String(value || "").trim());
  if (!m) return String(value || "");
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4] || 0), Number(m[5] || 0));
  const day = d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
  return m[4] ? `${day}, ${d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}` : day;
}

//: The people field: one chip per name and the field to type the next in,
//: Enter or a comma making a chip, Backspace in an empty field taking the
//: last. The note edit form's tag field (note-edit-panels.js), for names.
function meetingPeopleField(initial = []) {
  const people = [...initial];
  const field = document.createElement("div");
  field.className = "tag-field meeting-people prop-value";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "note-edit-tag-input";
  input.placeholder = "Add a name";
  input.autocomplete = "off";
  input.setAttribute("aria-label", "Who is in this meeting: type a name, then Enter");
  const draw = () => {
    for (const old of field.querySelectorAll(".chip")) old.remove();
    for (const name of people) {
      const person = chip(`ph:user ${name}`, "tag", () => {
        people.splice(people.indexOf(name), 1);
        draw();
        input.focus();
      });
      person.append(Object.assign(document.createElement("i"), { className: "ph ph-x" }));
      person.title = `Remove ${name}`;
      person.setAttribute("aria-label", `Remove ${name}`);
      field.insertBefore(person, input);
    }
  };
  const commit = () => {
    const typed = input.value.split(",").map((t) => t.trim().replace(/^@/, "")).filter(Boolean);
    input.value = "";
    for (const name of typed) if (!people.some((p) => p.toLowerCase() === name.toLowerCase())) people.push(name);
    draw();
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit();
    } else if (event.key === "Backspace" && !input.value && people.length) {
      people.pop();
      draw();
    }
  });
  //: A comma pasted or typed by a keyboard that sends no keydown for it.
  input.addEventListener("input", () => {
    if (input.value.includes(",")) commit();
  });
  input.addEventListener("blur", commit);
  field.appendChild(input);
  draw();
  return { field, input, read: () => (commit(), [...people]) };
}

function meetingFormRow(label, control, id) {
  const row = document.createElement("div");
  row.className = "prop-row";
  const name = document.createElement("label");
  name.className = "prop-key muted";
  name.textContent = label;
  if (id) {
    control.id = id;
    name.htmlFor = id;
  }
  row.append(name, control);
  return row;
}

//: **Every meeting act undoes** (WORLD_CLASS_PLAN 28.5 row 4, decision 53):
//: a note or a document it made goes to the bin and comes back, a reminder
//: likewise, and an addition puts the text back as it was. One pair per
//: kind, so each act names its words and two functions, nothing more.
//: Not an undo itself: the pair each act hands to `pushUndo`.
function meetingBinPair(kind, id, after = () => {}) {
  const base = kind === "note" ? "/entries" : kind === "document" ? "/documents" : "/reminders";
  const refresh = async () => {
    if (kind === "note") await refreshEntries([id]).catch(() => {});
    after();
  };
  return {
    undo: async () => {
      await apiJson(`${base}/${id}`, { method: "DELETE" });
      await refresh();
    },
    redo: async () => {
      await apiJson(`${base}/${id}/restore`, { method: "POST" });
      await refresh();
    },
  };
}

//: **New meeting** (decision 1): a sheet with what a meeting is named, when
//: it is and who is in it, then the note itself in the editor, where the
//: agenda, notes, decisions and action items are written. `notes` and
//: `then` are the recorder's: a recording saved as a new meeting arrives
//: with its transcript under Notes.
async function openNewMeeting({ title = "", notes = "", then = null } = {}) {
  //: One at a time: a double click on a Create row (whose dialog fades
  //: rather than vanishing) pressed it twice and stacked two sheets.
  if (document.querySelector('[data-sheet="new-meeting"]')) return;
  openSheet({
    label: "New meeting",
    sub: "A note with an agenda, notes, decisions and action items.",
    name: "new-meeting",
    build: (card, close) => {
      card.classList.add("inbox-card", "meeting-new");
      const body = document.createElement("div");
      body.className = "inbox-body";
      const titleInput = document.createElement("input");
      titleInput.type = "text";
      titleInput.maxLength = 200;
      titleInput.className = "prop-value";
      titleInput.placeholder = "Weekly sync";
      titleInput.value = title;
      const whenInput = document.createElement("input");
      whenInput.type = "datetime-local";
      whenInput.className = "prop-value";
      whenInput.value = meetingNowValue();
      const people = meetingPeopleField();
      //: The title's chips (quickadd.js): "Sync with Ana friday 2pm" sets When
      //: as it is read and names Ana; a chip pressed off puts When back.
      let typedWhen = whenInput.value;
      let chipWhen = false;
      whenInput.addEventListener("input", () => {
        typedWhen = whenInput.value;
        chipWhen = false;
      });
      body.append(
        meetingFormRow("Title", titleInput, "meeting-new-title"),
        meetingFormRow("When", whenInput, "meeting-new-when"),
        meetingFormRow("Who", people.field)
      );
      people.field.previousElementSibling.htmlFor = "meeting-new-people";
      people.input.id = "meeting-new-people";
      quickAddAttach(titleInput, "meeting", {
        after: titleInput.closest(".prop-row"),
        onSlots: (slots) => {
          if (slots?.date || slots?.time) {
            whenInput.value = `${slots.date || typedWhen.slice(0, 10)}T${slots.time || typedWhen.slice(11, 16)}`;
            chipWhen = true;
          } else if (chipWhen) {
            whenInput.value = typedWhen;
            chipWhen = false;
          }
        },
      });
      const status = document.createElement("p");
      status.className = "status";
      status.setAttribute("role", "status");
      const actions = document.createElement("div");
      actions.className = "row right space-dialog-actions";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "ghost small";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", close);
      const create = document.createElement("button");
      create.type = "button";
      create.className = "accent small";
      create.id = "meeting-new-create";
      setLabel(create, "ph:users-three Start the meeting");
      //: `record`: "Start and record" (INBOX 704: the redesign took the
      //: recorder's tile away and left recording two levels deep): the
      //: meeting is made, then the recorder opens writing into its Notes.
      const make = async (record = false) => {
        create.disabled = true;
        recordButton.disabled = true;
        status.classList.remove("error");
        let made = null;
        try {
          const slots = await quickAddSlots(titleInput);
          const attendees = people.read();
          for (const name of slots?.people || []) {
            if (!attendees.some((p) => p.toLowerCase() === name.toLowerCase())) attendees.push(name);
          }
          made = await apiJson("/meetings", {
            method: "POST",
            body: JSON.stringify({
              title: slots ? slots.title : titleInput.value.trim(),
              when: whenInput.value || "",
              attendees,
              notes,
            }),
          });
        } catch (error) {
          status.textContent = error.message || "Couldn't start the meeting.";
          status.classList.add("error");
          create.disabled = false;
          recordButton.disabled = false;
          return;
        }
        close();
        //: The one note it made, not a re-read of the notebook (the
        //: refresh ratchet, tests/test_refresh_entries.py).
        await refreshEntries([made.id]).catch(() => {});
        if (then) then(made);
        const binned = meetingBinPair("note", made.id);
        pushUndo("Started a meeting", binned.undo, binned.redo);
        //: Straight into the note: the meeting is where the writing happens.
        flashEntry(made.id);
        if (record) return meetingRecordInto(made.id);
        openNoteEditor(made.id);
        toastAction("Meeting started. Its action items, summary and recording are under its meeting chip.", "Open", () => openMeetingSheet(made.id));
      };
      const recordButton = document.createElement("button");
      recordButton.type = "button";
      recordButton.className = "ghost small";
      recordButton.id = "meeting-new-record";
      recordButton.title = "Start the meeting and transcribe it as it happens, on this computer";
      setLabel(recordButton, "ph:microphone Start and record");
      recordButton.addEventListener("click", () => make(true));
      create.addEventListener("click", () => make());
      for (const input of [titleInput, whenInput]) {
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            make();
          }
        });
      }
      actions.append(cancel, recordButton, create);
      card.append(body, status, actions);
      requestAnimationFrame(() => titleInput.focus());
    },
  });
}

//: An action item's row: the box (done or not), the task and its owner, and
//: the reminder it has or a press to make one. The row recipe (DESIGN.md, "A
//: row in a list"): mark, content, one actions cell centred on the row.
function meetingActionRow(entryId, item, redraw) {
  const li = document.createElement("li");
  li.className = "meeting-action";
  if (item.done) li.classList.add("is-done");
  const mark = document.createElement("i");
  mark.className = `ph ${item.done ? "ph-check-square" : "ph-square"} meeting-action-mark`;
  mark.setAttribute("aria-hidden", "true");
  const main = document.createElement("span");
  main.className = "meeting-action-main";
  const text = document.createElement("span");
  text.className = "meeting-action-text";
  text.textContent = item.text;
  main.appendChild(text);
  const facts = [];
  if (item.done) facts.push("Done");
  if (item.owner) facts.push(`Owner ${item.owner}`);
  if (item.reminder_due) {
    const due = parseServerTime(item.reminder_due) || new Date(item.reminder_due);
    facts.push(`Reminder ${due.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`);
  }
  if (facts.length) {
    const line = document.createElement("span");
    line.className = "muted meeting-action-facts";
    line.textContent = facts.join(" · ");
    main.appendChild(line);
  }
  const act = document.createElement("span");
  act.className = "meeting-action-act";
  if (item.reminder_id) {
    act.appendChild(smallButton("ph:alarm Show", "Open this reminder in Reminders", () => {
      switchTab("reminders");
    }));
  } else if (!item.done) {
    const remind = smallButton("ph:alarm Remind me", "Make this action item a reminder: when it says, or when you say", () => meetingRemind(entryId, item, remind, redraw));
    remind.classList.add("meeting-remind");
    act.appendChild(remind);
  }
  li.append(mark, main, act);
  return li;
}

async function meetingRemind(entryId, item, button, redraw, when = "") {
  button.disabled = true;
  try {
    const made = await apiJson(`/entries/${entryId}/meeting/remind`, {
      method: "POST",
      body: JSON.stringify({ line: item.line, when, tz_offset_minutes: -new Date().getTimezoneOffset() }),
    });
    const due = parseServerTime(made.due_at) || new Date(made.due_at);
    const binned = meetingBinPair("reminder", made.id, redraw);
    pushUndo("Made a reminder from an action item", binned.undo, binned.redo);
    toastAction(`Reminder set for ${due.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}.`, "Show", () => switchTab("reminders"));
    redraw();
  } catch (error) {
    button.disabled = false;
    //: The line says no time: ask for one, read by the same rules.
    if (error.status === 422 && !when) {
      const asked = await promptDialog(`When should “${item.text}” remind you?`, "tomorrow at 9am", { confirmLabel: "Remind me" });
      if (asked) return meetingRemind(entryId, item, button, redraw, asked);
      return;
    }
    toast(error.message || "Couldn't make that reminder.", true);
  }
}

//: **The meeting sheet**: when and who in its head, the action items, the
//: decisions, and three things to do with the meeting. Reached from the
//: meeting chip on the note's details line, the note's ⋯ menu, and after
//: New meeting.
async function openMeetingSheet(entryId) {
  let data = null;
  try {
    data = await apiJson(`/entries/${entryId}/meeting`);
  } catch (error) {
    toast(error.message || "Couldn't open that meeting.", true);
    return;
  }
  const entry = (typeof allEntries !== "undefined" ? allEntries : []).find((e) => e.id === entryId);
  const when = data.date ? meetingWhenText(data.date) : "No date yet";
  const who = data.attendees.length ? data.attendees.join(", ") : "nobody named yet";
  openSheet({
    label: entry?.title || "Meeting",
    sub: `${when} · ${who}`,
    name: "meeting",
    build: (card, close) => {
      card.classList.add("inbox-card", "meeting-view");
      const body = document.createElement("div");
      body.className = "inbox-body";
      const redraw = async () => {
        try {
          data = await apiJson(`/entries/${entryId}/meeting`);
        } catch {
          return;
        }
        fill();
      };
      const actionsHead = document.createElement("h3");
      actionsHead.textContent = "Action items";
      const actionsList = document.createElement("ul");
      actionsList.className = "meeting-actions-list";
      const decisionsHead = document.createElement("h3");
      decisionsHead.textContent = "Decisions";
      const decisionsList = document.createElement("ul");
      decisionsList.className = "meeting-decisions";
      const proposal = document.createElement("div");
      proposal.className = "meeting-proposal hidden";
      proposal.setAttribute("aria-live", "polite");
      const fill = () => {
        actionsList.replaceChildren();
        for (const item of data.actions) actionsList.appendChild(meetingActionRow(entryId, item, redraw));
        if (!data.actions.length) {
          const none = document.createElement("li");
          none.className = "muted meeting-empty";
          none.textContent = "None yet. Write them as “- [ ] Send the deck @Sam by Friday” under Action items.";
          actionsList.appendChild(none);
        }
        decisionsList.replaceChildren();
        for (const text of data.decisions) {
          const li = document.createElement("li");
          li.textContent = text;
          decisionsList.appendChild(li);
        }
        if (!data.decisions.length) {
          const none = document.createElement("li");
          none.className = "muted meeting-empty";
          none.textContent = "None yet. Write them under Decisions, or let Summarise find them in your notes.";
          decisionsList.appendChild(none);
        }
      };
      fill();
      body.append(actionsHead, actionsList, decisionsHead, decisionsList, proposal);

      const status = document.createElement("p");
      status.className = "status";
      status.setAttribute("role", "status");
      const bar = document.createElement("div");
      bar.className = "row right space-dialog-actions meeting-view-actions";
      const details = smallButton("ph:users Date and people", "Change when it was and who was there", () => {
        close();
        const target = (typeof allEntries !== "undefined" ? allEntries : []).find((e) => e.id === entryId);
        if (target) openNotePropertiesSheet(target);
      });
      const record = smallButton("ph:microphone Record into it", "Record, transcribe on this machine, and add the transcript under Notes", () => {
        close();
        meetingRecordInto(entryId);
      });
      const summarise = smallButton("ph:sparkle Summarise", "Find the decisions and action items in your notes, each with the words it came from", () =>
        meetingSummarise(entryId, proposal, status, summarise, redraw)
      );
      summarise.id = "meeting-summarise";
      bar.append(details, record, summarise);
      card.append(body, status, bar);
    },
  });
}

//: **Summarise** (decision 3): the server keeps only the lines whose source
//: words are in the note; this shows them with those words and adds them
//: only when asked, after the person's own lines, with Undo.
async function meetingSummarise(entryId, proposal, status, button, redraw) {
  button.disabled = true;
  status.classList.remove("error");
  setLabel(status, "ph:spin Reading your notes…");
  let result = null;
  try {
    result = await apiJson(`/entries/${entryId}/meeting/summarise`, { method: "POST" });
  } catch (error) {
    status.textContent = error.message || "Couldn't summarise this meeting.";
    status.classList.add("error");
    button.disabled = false;
    return;
  }
  button.disabled = false;
  const lines = [...result.lines.decisions, ...result.lines.actions];
  const dropped = result.dropped
    ? ` ${result.dropped === 1 ? "One line had" : `${result.dropped} lines had`} no source in your notes and ${result.dropped === 1 ? "was" : "were"} left out.`
    : "";
  //: With no model the rules read the notes (28.5 row 2), and the sheet
  //: says so in one line rather than going quiet.
  const how = result.note ? ` ${result.note}` : "";
  if (!lines.length) {
    status.textContent = `Nothing to add: no decision or action item was found in the notes.${dropped}${how}`;
    return;
  }
  status.textContent = result.note || "";
  proposal.replaceChildren();
  proposal.classList.remove("hidden");
  const head = document.createElement("p");
  head.className = "muted";
  head.textContent = `Found ${result.decisions.length} ${result.decisions.length === 1 ? "decision" : "decisions"} and ${result.actions.length} action ${result.actions.length === 1 ? "item" : "items"}, each with the words it came from.${dropped}`;
  const list = document.createElement("ul");
  list.className = "meeting-proposal-list";
  for (const item of [...result.decisions.map((d) => ({ ...d, kind: "Decision" })), ...result.actions.map((a) => ({ ...a, kind: "Action" }))]) {
    const li = document.createElement("li");
    const what = document.createElement("span");
    const named = item.owner && item.text.includes(`@${item.owner}`);
    const facts = [named ? "" : item.owner, item.due].filter(Boolean).join(", ");
    what.textContent = `${item.kind}: ${item.text}${facts ? ` (${facts})` : ""}`;
    const cite = document.createElement("q");
    cite.className = "muted meeting-cite";
    cite.textContent = item.quote;
    li.append(what, cite);
    list.appendChild(li);
  }
  const row = document.createElement("div");
  row.className = "row right";
  const discard = smallButton("Discard", "Leave the note as it is", () => {
    proposal.classList.add("hidden");
    proposal.replaceChildren();
  });
  const add = smallButton("ph:plus Add to the meeting", "Add these after your own lines under Decisions and Action items", async () => {
    add.disabled = true;
    try {
      const before = await apiJson(`/entries/${entryId}`);
      const send = (section, items) =>
        items.length
          ? apiJson(`/entries/${entryId}/meeting/append`, { method: "POST", body: JSON.stringify({ section, lines: items }) })
          : null;
      await send("Decisions", result.lines.decisions);
      await send("Action items", result.lines.actions);
      const undo = async () => {
        await apiJson(`/entries/${entryId}`, { method: "PUT", body: JSON.stringify({ content: before.content }) });
        await refreshEntries([entryId]);
      };
      const redo = async () => {
        await send("Decisions", result.lines.decisions);
        await send("Action items", result.lines.actions);
        await refreshEntries([entryId]);
      };
      pushUndo("Added the meeting summary", undo, redo);
      toastAction("Added to the meeting.", "Undo", async () => {
        await undo();
        redraw();
      });
      proposal.classList.add("hidden");
      proposal.replaceChildren();
      await refreshEntries([entryId]).catch(() => {});
      redraw();
    } catch (error) {
      add.disabled = false;
      toast(error.message || "Couldn't add that.", true);
    }
  }, false);
  add.classList.add("accent");
  row.append(discard, add);
  proposal.append(head, list, row);
}

//: **A recording saved** (media.js's Save as a meeting / Add to the meeting):
//: under the Notes of the meeting it was opened from, after what is already
//: there, or a new meeting in the one shape dated now with the transcript
//: under Notes. The uncited summary this save used to prepend is gone: a
//: line nobody can check against the transcript is not one to file under
//: the person's name; the meeting sheet's Summarise cites every line.
async function meetingSaveTranscript(content, title, target) {
  const status = $("meeting-status");
  const button = $("meeting-save");
  button.disabled = true;
  status.classList.remove("error");
  setLabel(status, "ph:spin Saving…");
  try {
    const saved = target !== null ? await meetingAppendUndoable(target, content) : await meetingCreateUndoable(content, title);
    await loadEntries();
    meetingAcceptOriginal();
    meetingShowSaved(content, "Open the meeting", () => openMeetingSheet(saved.id), target !== null ? "Added under the meeting's Notes." : "Saved as a meeting. Summarise finds its decisions and action items.");
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  } finally {
    button.disabled = false;
  }
}

//: Under the meeting's Notes, with Undo putting the note back as it was.
async function meetingAppendUndoable(target, content) {
  const before = await apiJson(`/entries/${target}`);
  const append = () => apiJson(`/entries/${target}/meeting/append`, { method: "POST", body: JSON.stringify({ section: "Notes", lines: [content] }) });
  const saved = await append();
  pushUndo(
    "Added a transcript to the meeting",
    async () => {
      await apiJson(`/entries/${target}`, { method: "PUT", body: JSON.stringify({ content: before.content }) });
      await refreshEntries([target]).catch(() => {});
    },
    async () => {
      await append();
      await refreshEntries([target]).catch(() => {});
    }
  );
  return saved;
}

//: A new meeting with the transcript under Notes, binned by Undo.
async function meetingCreateUndoable(content, title) {
  const saved = await apiJson("/meetings", {
    method: "POST",
    body: JSON.stringify({ title: title || `Recording ${new Date().toLocaleDateString()}`, when: meetingNowValue(), notes: content }),
  });
  const binned = meetingBinPair("note", saved.id);
  pushUndo("Saved a recording as a meeting", binned.undo, binned.redo);
  //: The meeting is saved; only the recording's link to it can fail, and the person is told why.
  if (meetingTake.id) apiJson(`/recordings/${meetingTake.id}`, { method: "PATCH", body: JSON.stringify({ entry_id: saved.id }) }).catch((error) => toast(error.message, true));
  return saved;
}

//: The recorder, aimed at one meeting: its transcript goes under that
//: meeting's Notes. `.meeting-into` hides the name field (the meeting has
//: its name) and swaps the save's words (02-chat-graph.css).
function meetingRecordInto(entryId) {
  openMeetingRecorder();
  $("meeting-overlay").dataset.target = String(entryId);
  $("meeting-overlay").classList.add("meeting-into");
}

//: Moved from media.js (boot) on 2026-10-06: the recorder is only reached
//: through openMeetingRecorder, a stand-in in LAZY_ENTRY_POINTS.meetings.
// --- meeting notes (§17) -------------------------------------------------------------
//
// The backlog's own "highest-value single addition still unbuilt": the quick
// microphone button above is sized for a spoken note (server caps it at 25MB,
// `routes_voice.py`'s own comment says "a spoken note, not a podcast"), a
// meeting or a lecture needs a separate flow with its own recording cap, a
// visible elapsed timer so a long recording doesn't feel stalled, and a
// review step before the transcript becomes a note, the same "you're in
// control before it's saved" shape the persona-peek and compression-summary
// features already use elsewhere.
//
// **A recording is a meeting's, not a note of its own** (INBOX 644). Saved,
// a transcript becomes a meeting note in the one shape (`POST /meetings`,
// the transcript under Notes), or goes under Notes of the meeting it was
// opened from (`openMeetingRecorder({ entryId })`, the meeting sheet's
// Record into it). The action items and decisions are the meeting sheet's
// (meetings.js): each item a reminder on demand, and Summarise, whose every
// line carries the words it came from. The uncited summary this save used
// to prepend is gone: a line nobody can check against the transcript is
// not one to file under the person's name. faster-whisper is not installed
// in the sandbox, so the transcription itself is untested past its request
// shape (CLAUDE.md's standing caveat).

let meetingRecorder = null;
let meetingStream = null;
let meetingChunks = [];
let meetingTimerHandle = null;
let meetingStartedAt = 0;

//: **The recording in hand is an object** (WORLD_CLASS_PLAN 28.5 row 1,
//: decision 2): made on the server before the first sound (`POST
//: /recordings`), its audio appended as it arrives, finished on Stop with its
//: length, the waveform the recorder drew and the markers pressed. So Record
//: never refuses: with no Whisper add-on the audio is kept and the sheet says
//: how long it is; transcription is offered only when `/voice/status` says
//: the add-on is there. One object, not more top-level lets.
const meetingTake = { id: null, chain: Promise.resolve(), failed: null, peaks: [], markers: [], ms: 0 };

//: How long the audio is, in ms: the clock stops while paused.
function meetingElapsedMs() {
  const end = meetingRecorder?.state === "paused" ? meetingPausedAt : Date.now();
  return Math.max(0, end - meetingStartedAt);
}

function meetingClockText(ms) {
  const seconds = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

function meetingElapsedText() {
  return meetingClockText(Date.now() - meetingStartedAt);
}

//: The container's own name for the sheet (decision 3: what the browser made, by its own name).
function meetingContainerName(mime) {
  return (String(mime || "").split(";")[0].split("/")[1] || "audio").replace(/^x-/, "");
}

async function meetingTakeBegin(recorder) {
  Object.assign(meetingTake, { id: null, chain: Promise.resolve(), failed: null, peaks: [], markers: [], ms: 0 });
  const made = await apiJson("/recordings", {
    method: "POST",
    body: JSON.stringify({
      title: ($("meeting-title")?.value || "").trim() || `Recording ${whenText()}`,
      mime: recorder.mimeType || "audio/webm",
      entry_id: Number($("meeting-overlay").dataset.target) || null,
    }),
  });
  meetingTake.id = made.id;
}

const MEETING_CHUNK_MS = 10000;

//: One slice of audio onto the object, in order: each waits for the last.
function meetingTakeAppend(blob) {
  const id = meetingTake.id;
  if (!id || !blob?.size) return;
  const form = new FormData();
  form.append("file", blob, "chunk");
  form.append("duration_ms", String(Math.round(meetingElapsedMs())));
  meetingTake.chain = meetingTake.chain
    .then(() => api.upload(`/recordings/${id}/chunk`, form))
    .catch((error) => {
      meetingTake.failed = error;
    });
}

//: The waveform kept with the object: the recorder's levels, the loudest of
//: each of up to 400 buckets, 0 to 100.
function meetingPeaksSummary(levels, size = 400) {
  if (levels.length <= size) return levels.map((v) => Math.round(v * 100));
  const out = [];
  const step = levels.length / size;
  for (let i = 0; i < size; i++) {
    const slice = levels.slice(Math.floor(i * step), Math.floor((i + 1) * step));
    out.push(Math.round(Math.max(0, ...slice) * 100));
  }
  return out;
}

async function meetingTakeFinish() {
  await meetingTake.chain;
  if (meetingTake.failed) throw meetingTake.failed;
  return apiJson(`/recordings/${meetingTake.id}/finish`, {
    method: "POST",
    body: JSON.stringify({ duration_ms: meetingTake.ms, peaks: meetingPeaksSummary(meetingTake.peaks), markers: meetingTake.markers }),
  });
}

//: How many amplitude samples the waveform holds. About four seconds at the
//: sample rate below, which is enough to see the shape of a sentence without
//: the line becoming a texture.
const MEETING_WAVE_POINTS = 140;
//: Frames between samples. Every frame would fill the window in two seconds
//: and spend a redraw on a difference nobody can see.
const MEETING_WAVE_EVERY = 3;
//: With reduced motion (V4): a level bar stepping four times a second at 60 fps.
const MEETING_WAVE_STILL_EVERY = 15;

//: Kept at module level so `closeMeetingRecorder` can stop a draw loop that
//: `toggleMeetingRecording` started: the two are different user actions and
//: neither can reach the other's locals.
let stopMeetingWave = () => {};

// The line that moves while you talk. See the note in index.html for why the
// six-bar meter on the Record button was not enough: a recording with no
// visible response to your voice is indistinguishable from a broken
// microphone, and that is what was actually being reported.
function startMeetingWave(stream) {
  const canvas = document.getElementById("meeting-wave");
  if (!canvas) return () => {};
  let ctx;
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
  } catch {
    return () => {}; // no Web Audio: the recording itself is unaffected
  }
  const analyser = ctx.createAnalyser();
  // 2048 in the *time* domain: this draws a level line, and a bigger window
  // gives a steadier RMS than the 256-bin frequency analyser the button meter
  // uses. Both can run at once, they are separate nodes on the same stream.
  analyser.fftSize = 2048;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const samples = new Uint8Array(analyser.fftSize);
  const levels = new Array(MEETING_WAVE_POINTS).fill(0);

  const paint = canvas.getContext("2d");
  canvas.classList.remove("hidden");
  // Size the backing store to the box it is actually drawn in, at the
  // device's own pixel density. The markup's 960×120 is a fallback for the
  // frame before layout; leaving it there stretches the line horizontally and
  // makes it soft on any HiDPI screen. Measured after `remove("hidden")`, 
  // a hidden element has no width to read.
  const box = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  if (box.width) {
    canvas.width = Math.round(box.width * ratio);
    canvas.height = Math.round(box.height * ratio);
  }
  let frame = null;
  let ticks = 0;
  let stopped = false;
  //: **Reduced motion is a still meter** (V4): no line scrolling past, one
  //: bar from the middle whose length is the level now.
  const still = reducedMotionWanted();
  canvas.dataset.mode = still ? "meter" : "line";
  const ink = () => getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#4664f0";

  function drawStill(level) {
    const { width, height } = canvas;
    paint.clearRect(0, 0, width, height);
    const bar = Math.max(4, height * 0.18);
    const length = Math.max(bar, level * width);
    paint.fillStyle = ink();
    paint.globalAlpha = 0.18;
    paint.fillRect(0, (height - bar) / 2, width, bar);
    paint.globalAlpha = 1;
    paint.fillRect((width - length) / 2, (height - bar) / 2, length, bar);
  }

  function draw() {
    const { width, height } = canvas;
    const middle = height / 2;
    paint.clearRect(0, 0, width, height);
    // The accent, read from the live stylesheet rather than hard-coded, so
    // the line follows whatever theme is set, including a custom one.
    paint.strokeStyle = ink();
    paint.lineWidth = 2;
    paint.lineJoin = "round";
    paint.lineCap = "round";
    const step = width / (levels.length - 1);
    // Two mirrored strokes rather than one: a level line drawn only upward
    // reads as a graph, and the symmetrical pair reads as sound.
    for (const direction of [-1, 1]) {
      paint.beginPath();
      levels.forEach((level, i) => {
        const y = middle + direction * level * (middle - 4);
        if (i === 0) paint.moveTo(0, y);
        else paint.lineTo(i * step, y);
      });
      paint.stroke();
    }
  }

  function tick() {
    if (stopped) return;
    if (ticks % (still ? MEETING_WAVE_STILL_EVERY : MEETING_WAVE_EVERY) === 0) {
      analyser.getByteTimeDomainData(samples);
      // RMS around the 128 midpoint, the honest measure of loudness, and
      // steadier than a peak, which flickers on consonants.
      let sum = 0;
      for (let i = 0; i < samples.length; i++) {
        const value = (samples[i] - 128) / 128;
        sum += value * value;
      }
      const rms = Math.sqrt(sum / samples.length);
      // sqrt again for the same reason the bar meter gives: ordinary speech
      // sits low in the range and a linear map leaves it near the floor.
      const level = Math.min(1, Math.sqrt(rms) * 1.6);
      levels.push(level);
      levels.shift();
      //: Every level, not only the window drawn: the saved waveform (row 6),
      //: repeated while the meter is still, so the saved density matches.
      if (meetingRecorder?.state === "recording") {
        for (let i = 0; i < (still ? MEETING_WAVE_STILL_EVERY / MEETING_WAVE_EVERY : 1); i++) meetingTake.peaks.push(level);
      }
      canvas.dataset.level = level.toFixed(3);
      if (still) drawStill(level);
      else draw();
    }
    ticks++;
    frame = requestAnimationFrame(tick);
  }

  // Chrome creates an AudioContext suspended even inside a click handler, and
  // the analyser reads all-zero until it is running, the same trap the bar
  // meter documents. Start the loop after resume resolves.
  ctx.resume().then(tick, tick);

  return () => {
    stopped = true;
    if (frame) cancelAnimationFrame(frame);
    ctx.close().catch(() => {});
    canvas.classList.add("hidden");
    paint.clearRect(0, 0, canvas.width, canvas.height);
  };
}

function stopMeetingTimer() {
  if (meetingTimerHandle) clearInterval(meetingTimerHandle);
  meetingTimerHandle = null;
}

//: **One state at a time** (INBOX 708, "these panels feel badly designed and
//: neglected"). The recorder was five things on screen at once whatever it was
//: doing: a Record button that was sometimes Stop, a clock reading 0:00 before
//: anything had started, a Pause that said Resume after the recording it
//: belonged to had ended, and a transcript box twelve rem tall around one
//: sentence. Now the card says which state it is in (`data-state`) and shows
//: only what that state needs:
//:   ready          Record (the one filled control)
//:   recording      Stop (filled), Pause, the clock, the level line
//:   paused         Stop (filled), Resume, the clock stopped
//:   transcribing   a progress bar and how long the audio was
//:   review         the transcript, sized to its words, and the save actions
//:   saved          the recording kept with its length (no add-on, or no
//:                  words heard), and Record for the next one
function setMeetingState(state) {
  $("meeting-card").dataset.state = state;
  const live = state === "recording" || state === "paused";
  $("meeting-stage").classList.toggle("hidden", state === "review" || state === "done");
  $("meeting-done")?.classList.toggle("hidden", state !== "done");
  $("meeting-controls").classList.toggle("hidden", !(live || state === "ready" || state === "saved"));
  $("meeting-pause").classList.toggle("hidden", !live);
  $("meeting-marker").classList.toggle("hidden", !live);
  $("meeting-timer").classList.toggle("hidden", !live);
  $("meeting-progress").classList.toggle("hidden", state !== "transcribing");
  //: The live words stay up while the full pass runs, then review replaces them (V5).
  $("meeting-live")?.classList.toggle("hidden", !(live || state === "transcribing") || !$("meeting-live").textContent);
  $("meeting-stop-transcribe")?.classList.toggle("hidden", state !== "transcribing");
  $("meeting-discard-take")?.classList.toggle("hidden", !live);
  $("meeting-captions")?.classList.toggle("hidden", live || state === "transcribing");
  const review = state === "review";
  $("meeting-transcript").classList.toggle("hidden", !review);
  $("meeting-save-row").classList.toggle("hidden", !review);
  stagePrimary("meeting-save", "meeting-done-open", state === "done");
  stagePrimary("meeting-record", "meeting-save", review);
  syncRecordingDock();
}

//: **A recording outlives its dialog** (UI_MODERNISATION V1, INBOX 828):
//: closed while recording, the dialog folds into this dock over every
//: surface, with the clock, Pause and Stop, and Open to bring it back.
function syncRecordingDock() {
  const dock = $("recording-dock");
  if (!dock) return;
  const state = $("meeting-card").dataset.state;
  const live = state === "recording" || state === "paused";
  const shown = live && $("meeting-overlay").classList.contains("hidden");
  //: Its place over every surface is the captions dock's rule (captions-lazy.css).
  if (shown) ensureModule("captions");
  dock.classList.toggle("hidden", !shown);
  dock.classList.toggle("is-paused", state === "paused");
  setLabel($("recording-dock-pause"), state === "paused" ? "ph:play Resume" : "ph:pause Pause");
  $("recording-dock-title").textContent = ($("meeting-title")?.value || "").trim() || "Recording";
}

//: The clock in the dialog and the dock, from one place.
function meetingTick() {
  const text = meetingElapsedText();
  $("meeting-timer").textContent = text;
  if ($("recording-dock-time")) $("recording-dock-time").textContent = text;
}

// Resets the overlay to "ready to record", whether it's opening fresh or
// coming back after a discard, the same state either way.
function resetMeetingUI() {
  stopMeetingTimer();
  $("meeting-timer").textContent = "0:00";
  $("meeting-status").textContent = "";
  $("meeting-status").classList.remove("error");
  $("meeting-transcript").value = "";
  if ($("meeting-live")) $("meeting-live").textContent = "";
  $("meeting-record").disabled = false;
  $("meeting-record").classList.remove("recording");
  setLabel($("meeting-record"), "ph:record Record");
  setLabel($("meeting-pause"), "ph:pause Pause");
  $("meeting-wave")?.classList.add("hidden");
  setMeetingState("ready");
}

//: The meeting a recording goes into, or null for a new one: set by the
//: meeting sheet's Record into it (meetings.js `meetingRecordInto`), which
//: also puts `.meeting-into` on the overlay (the name field goes, the save
//: says where the words land). Every other way in is a new meeting.
//: Held on the overlay (`data-target`), not a top-level `let` (the
//: global-scope ratchet).

async function openMeetingRecorder() {
  //: A recording folded into the dock is brought back, not reset.
  if (meetingRecorder) return showMeetingRecorder();
  nameMeetingMic();
  overlayReturnFocus = document.activeElement;
  delete $("meeting-overlay").dataset.target;
  $("meeting-overlay").classList.remove("meeting-into", "voice-note");
  resetMeetingUI();
  $("meeting-overlay").classList.remove("hidden");
  $("meeting-record").focus();
}

//: **Voice note** (WORLD_CLASS_PLAN 28.5 row 3; the owner: "meeting notes
//: should be different ... from dictation"): a memo, not a meeting. The same
//: recorder and the same kept object, its head saying Voice note, and its
//: transcript, when the add-on makes one, saved as a plain note rather than
//: a meeting. Dictation is the composer's mic, which types into the box.
function openVoiceNote() {
  openMeetingRecorder();
  $("meeting-overlay").classList.add("voice-note");
}

function showMeetingRecorder() {
  $("meeting-overlay").classList.remove("hidden");
  syncRecordingDock();
  $("meeting-record").focus();
}

//: Closed while recording, the recording goes on in the dock (V1): a live
//: microphone is never ownerless, because the dock says it is listening and
//: stops it. Discard is the way to throw a take away
//: (`discardMeetingTake`). Closed in any other state the dialog just goes;
//: a transcription carries on in the background.
function closeMeetingRecorder() {
  if (meetingRecorder && meetingRecorder.state !== "inactive") {
    $("meeting-overlay").classList.add("hidden");
    syncRecordingDock();
    overlayReturnFocus?.focus?.();
    overlayReturnFocus = null;
    return;
  }
  $("meeting-overlay").classList.add("hidden");
  overlayReturnFocus?.focus?.();
  overlayReturnFocus = null;
}

//: Discard while recording: what was sent goes to the bin, not nowhere.
function discardMeetingTake() {
  if (meetingRecorder && meetingRecorder.state !== "inactive") {
    // A discard is not transcribed: the stop listener reads this (`onstop = null`
    // here removed nothing, the listener is an `addEventListener` one).
    meetingRecorder.discarded = true;
    meetingRecorder.stop();
  }
  meetingStream?.getTracks().forEach((t) => t.stop());
  stopMeetingWave();
  stopMeetingWave = () => {};
  meetingRecorder = null;
  meetingStream = null;
  stopMeetingTimer();
  resetMeetingUI();
  meetingSay("Discarded. The audio is in the bin.");
}

async function toggleMeetingRecording() {
  const button = $("meeting-record");
  if (meetingRecorder) {
    button.disabled = true; // one press, not a double-fire while it stops
    // The clock keeps the length of the audio: stopped while recording it is
    // up to a second stale, stopped while paused it is already right.
    if (meetingRecorder.state === "recording") $("meeting-timer").textContent = meetingElapsedText();
    meetingTake.ms = Math.round(meetingElapsedMs());
    // A paused recorder holds what it has heard so far; asking for it before
    // the stop makes the last chunk arrive on every engine, not only the ones
    // that flush on a stop from paused (INBOX 708: Stop from Paused).
    if (meetingRecorder.state === "paused") meetingRecorder.requestData();
    meetingRecorder.stop();
    return;
  }
  //: Asked now, used after Stop: transcription is offered only when the
  //: add-on is there, and its absence no longer stops a recording (row 1).
  if (voiceStatus === null) {
    voiceStatus = await apiJson("/voice/status").catch(() => ({ available: false }));
  }
  try {
    meetingStream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraints() });
  } catch {
    meetingSay("Microphone access was blocked, allow it in your browser.", true);
    return;
  }
  const recorder = new MediaRecorder(meetingStream);
  try {
    await meetingTakeBegin(recorder);
  } catch (error) {
    meetingStream.getTracks().forEach((t) => t.stop());
    meetingStream = null;
    meetingSay(error.message || "Couldn't start a recording.", true);
    return;
  }
  meetingChunks = [];
  meetingRecorder = recorder;
  recorder.addEventListener("dataavailable", (e) => {
    meetingChunks.push(e.data);
    if (!recorder.discarded) meetingTakeAppend(e.data);
  });
  recorder.addEventListener("stop", () => meetingRecordingStopped(recorder, button));
  //: A slice every 10 s, each appended to the object as it arrives (row 5):
  //: a tab killed at 2:00 keeps at least 1:50.
  recorder.start(MEETING_CHUNK_MS);
  meetingRecordingStarted(button);
}

function meetingSay(text, error = false) {
  $("meeting-status").textContent = text;
  $("meeting-status").classList.toggle("error", error);
}

function meetingRecordingStarted(button) {
  meetingStartedAt = Date.now();
  $("meeting-timer").textContent = meetingElapsedText();
  meetingTimerHandle = setInterval(meetingTick, 1000);
  button.classList.add("recording");
  setLabel(button, "ph:stop Stop");
  // Appended after setLabel, not before: setLabel's replaceChildren() wipes
  // every child on the button, and the bar meter startMicLevelMeter() builds
  // is one: appending it earlier just got it discarded a line later.
  const stopLevel = startMicLevelMeter(meetingStream, button);
  const stopWave = startMeetingWave(meetingStream);
  stopMeetingWave = () => {
    stopLevel();
    stopWave();
  };
  setMeetingState("recording");
  meetingSay("Recording. Saved as it goes.");
  meetingLiveWordsStart();
}

// --- live words while recording (UI_MODERNISATION V5) ------------------------
//
// The captions pipeline (captions.js) borrows the recorder's stream and
// paints its last lines here as they are spoken; nothing is saved from it.
// The full pass after Stop replaces them in review. Without the captions
// helper the line says where to get it, once, muted.

const meetingLive = { on: false };

function meetingLiveWords(lines, running) {
  const box = $("meeting-live");
  box.classList.remove("muted");
  box.textContent = [...lines.slice(-2), running].filter(Boolean).join(" ") || "Listening…";
}

async function meetingLiveWordsStart() {
  const box = $("meeting-live");
  box.textContent = "";
  box.classList.remove("hidden");
  if (!(await ensureModule("captions")) || !meetingStream) return;
  const ok = await startLiveCaptions({ stream: meetingStream, into: meetingLiveWords, save: false, quiet: true });
  if (ok === true) {
    meetingLive.on = true;
    if (!meetingRecorder) meetingLiveWordsStop();
    return;
  }
  box.classList.add("muted");
  box.textContent = `Live words while recording: ${ok}`;
}

function meetingLiveWordsStop() {
  if (!meetingLive.on) return;
  meetingLive.on = false;
  stopRecorderWords();
}

//: Stop: the object is finished first, so the audio is kept whatever the
//: transcription does; then the add-on transcribes it, or the sheet says
//: how long the kept recording is.
async function meetingRecordingStopped(recorder, button) {
  if (meetingLive.on) {
    meetingLive.on = false;
    stopRecorderWords();
  }
  meetingStream?.getTracks().forEach((t) => t.stop());
  stopMeetingWave();
  stopMeetingWave = () => {};
  meetingStream = null;
  meetingRecorder = null;
  stopMeetingTimer();
  if (recorder.discarded) return meetingTakeDiscard();
  button.classList.remove("recording");
  setLabel(button, "ph:record Record");
  setLabel($("meeting-pause"), "ph:pause Pause");
  button.disabled = false;
  setMeetingState("transcribing");
  meetingSay("Saving the recording…");
  let saved = null;
  try {
    saved = await meetingTakeFinish();
  } catch (error) {
    setMeetingState("ready");
    meetingSay(error.message || "Couldn't save the recording.", true);
    return;
  }
  saved = await meetingEnhanceTake(saved);
  const length = meetingClockText(saved.duration_ms);
  const away = $("meeting-overlay").classList.contains("hidden");
  pushBinPairUndo(`Recorded ${length}`, `/recordings/${saved.id}`, `/recordings/${saved.id}/restore`, true, () => (typeof loadLibrary === "function" ? loadLibrary() : null));
  if (!voiceStatus?.available) {
    setMeetingState("saved");
    meetingSay(`Saved a ${length} recording (${meetingContainerName(saved.mime)}). Transcribing it needs the Voice notes add-on, in Settings, Packages.`);
    //: Stopped from the dock: the dialog is not on screen to say so.
    if (away) toastAction(`Saved “${saved.title || "Recording"}”, ${length}.`, "Open", () => openRecordings(saved.id));
    return;
  }
  return meetingTranscribeTake(saved, length);
}

//: **Transcribed in the background** (V1): the run is the server's, so
//: closing this dialog never stops it. While it is open the bar shows how far
//: it is and Stop ends it; done with the dialog still on this take, the
//: transcript comes back here to review; otherwise a notification says so.
async function meetingTranscribeTake(saved, length) {
  meetingSay(`Saved a ${length} recording. Transcribing it in the background: close this if you like, you will be told when it is done.`);
  const progress = $("meeting-progress");
  progress.removeAttribute("value");
  try {
    await startRecordingTranscription(saved, {
      progress: (run) => {
        if (meetingTake.id !== saved.id || run.progress == null) return;
        progress.max = 1;
        progress.value = run.progress;
        meetingSay(`Transcribing ${length}: ${Math.round(run.progress * 100)}%. Close this if you like; you will be told when it is done.`);
      },
      here: () => meetingTake.id === saved.id && !$("meeting-overlay").classList.contains("hidden") && $("meeting-card").dataset.state === "transcribing",
      done: async (run) => {
        const body = await apiJson(`/recordings/${saved.id}/transcript`).catch(() => ({ segments: [] }));
        const text = body.segments.map((seg) => seg.text).join(" ").trim();
        if (!text) {
          setMeetingState("saved");
          return meetingSay(`Nothing was heard in that recording. The ${length} of audio is kept in Recordings.`);
        }
        meetingSay(`Transcript of ${length}. Read it, trim it, then save. The audio is kept in Recordings.`);
        $("meeting-transcript").value = text;
        setMeetingState("review");
        autoGrow($("meeting-transcript"));
        $("meeting-transcript").focus();
      },
      ended: (run) => {
        if (meetingTake.id !== saved.id) return;
        setMeetingState("saved");
        if (run.state === "failed") meetingSay(`Saved a ${length} recording, but it couldn't be transcribed: ${run.error}`, true);
        else meetingSay(`Stopped transcribing. The ${length} of audio is kept in Recordings; Transcribe in its menu starts again.`);
      },
    });
  } catch (error) {
    setMeetingState("saved");
    meetingSay(`Saved a ${length} recording, but it couldn't be transcribed: ${error.message}`, true);
  }
}

// --- enhancement on save (UI_MODERNISATION V3, INBOX 828) -------------------
//
// The kept audio, cleaned in the page: a 80 Hz high-pass for rumble and
// handling noise, then one gain that brings speech to about -20 dBFS RMS,
// never past -1 dBFS peak nor by more than 20 dB. Written as 16 kHz mono
// wav (what Whisper reads, and the one container a page can write) to a new
// object pointing at the original, which is binned when the transcript is
// saved and kept otherwise. Takes over ENHANCE_MAX_MS are left as recorded:
// decoding an hour in the page would hold about 700 MB.

const ENHANCE_RATE = 16000;
const ENHANCE_TARGET_RMS = 0.1;
const ENHANCE_PEAK = 0.89;
const ENHANCE_MAX_GAIN = 10;
const ENHANCE_MAX_MS = 30 * 60 * 1000;

//: The gain for one channel of samples: the RMS of the frames above a
//: -50 dBFS gate (so silence does not pull speech up too far), bounded.
function enhanceGain(data) {
  const frame = 1600;
  let sum = 0;
  let count = 0;
  let peak = 0;
  for (let at = 0; at < data.length; at += frame) {
    let local = 0;
    const end = Math.min(data.length, at + frame);
    for (let i = at; i < end; i++) {
      local += data[i] * data[i];
      peak = Math.max(peak, Math.abs(data[i]));
    }
    if (Math.sqrt(local / (end - at)) > 0.003) {
      sum += local;
      count += end - at;
    }
  }
  if (!count || !peak) return 1;
  const rms = Math.sqrt(sum / count);
  return Math.min(ENHANCE_TARGET_RMS / rms, ENHANCE_PEAK / peak, ENHANCE_MAX_GAIN);
}

async function enhanceRecording(rec) {
  const buffer = await (await api(`/media/recordings/${rec.id}`)).arrayBuffer();
  const probe = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 1, 44100);
  const decoded = await probe.decodeAudioData(buffer);
  const offline = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, Math.ceil(decoded.duration * ENHANCE_RATE), ENHANCE_RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  const filter = offline.createBiquadFilter();
  filter.type = "highpass";
  filter.frequency.value = 80;
  filter.Q.value = Math.SQRT1_2;
  source.connect(filter);
  filter.connect(offline.destination);
  source.start();
  const rendered = await offline.startRendering();
  const data = rendered.getChannelData(0);
  const gain = enhanceGain(data);
  for (let i = 0; i < data.length; i++) data[i] *= gain;
  const wav = recordingWav(rendered, 0, rendered.duration);
  const made = await apiJson("/recordings", {
    method: "POST",
    body: JSON.stringify({ title: rec.title, mime: "audio/wav", source_id: rec.id, entry_id: rec.entry_id, derived: "enhanced" }),
  });
  const form = new FormData();
  form.append("file", wav, "enhanced.wav");
  form.append("duration_ms", String(rec.duration_ms));
  await api.upload(`/recordings/${made.id}/chunk`, form);
  const done = await apiJson(`/recordings/${made.id}/finish`, {
    method: "POST",
    body: JSON.stringify({ duration_ms: rec.duration_ms, peaks: rec.peaks, markers: rec.marks || rec.markers }),
  });
  done.enhanceGain = gain;
  return done;
}

//: After Stop: the cleaned copy becomes the take, the original is held
//: (`meetingTake.originalId`) until the transcript is saved. Any failure
//: keeps the recording as it was made and says so in the status line.
async function meetingEnhanceTake(saved) {
  meetingTake.originalId = null;
  if (!prefs.bool("micEnhance", true) || !saved.duration_ms || saved.duration_ms > ENHANCE_MAX_MS) return saved;
  meetingSay("Enhancing the audio…");
  try {
    const clean = await enhanceRecording(saved);
    meetingTake.originalId = saved.id;
    meetingTake.id = clean.id;
    return clean;
  } catch {
    meetingSay("Couldn't enhance the audio; it is kept as recorded.");
    return saved;
  }
}

//: The transcript is saved: the original of an enhanced take goes to the bin.
function meetingAcceptOriginal() {
  const id = meetingTake.originalId;
  meetingTake.originalId = null;
  if (id) apiJson(`/recordings/${id}`, { method: "DELETE", silent: true }).catch((e) => console.warn("The abandoned take was not removed:", e.message));
}

// --- after saving (UI_MODERNISATION V7) --------------------------------------
//
// A save no longer drops the dialog on whatever was behind it: it shows what
// was kept, the transcript's first lines, with Open and Record another.

const MEETING_DONE_LINES = 3;

function meetingShowSaved(text, label, open, said = "Saved. The audio is kept in Recordings.") {
  const lines = String(text).split(/\n+|(?<=[.?])\s+/).map((line) => line.trim()).filter(Boolean);
  const shown = lines.slice(0, MEETING_DONE_LINES).join(" ");
  $("meeting-done-lines").textContent = lines.length > MEETING_DONE_LINES ? `${shown} …` : shown;
  setLabel($("meeting-done-open"), `ph:arrow-square-out ${label}`);
  $("meeting-done").openSaved = open;
  setMeetingState("done");
  meetingSay(said);
  $("meeting-done-open").focus();
}

//: The dialog's Stop while transcribing.
async function stopMeetingTranscription() {
  if (meetingTake.id) await stopRecordingTranscription(meetingTake.id);
}

//: Closed while recording: what was sent goes to the bin, not nowhere, so
//: the close is undoable (the bin takes deletes).
async function meetingTakeDiscard() {
  const id = meetingTake.id;
  if (!id) return;
  try {
    await meetingTakeFinish();
    await apiJson(`/recordings/${id}`, { method: "DELETE" });
    pushBinPairUndo("Discarded a recording", `/recordings/${id}`, `/recordings/${id}/restore`, false, () => (typeof loadLibrary === "function" ? loadLibrary() : null));
  } catch {
    // An empty take is removed by its finish; nothing is left to bin.
  }
}

// Pause and resume, which a MediaRecorder supports directly, the chunks
// simply stop arriving and the recording continues where it left off. Asked
// for as part of "expanded as a proper feature with more capabilities", and
// it is the one a real meeting needs: someone leaves the room, a side
// conversation starts, and the alternative today is stopping and starting a
// second recording that transcribes as a separate transcript.
//
// The elapsed timer is corrected on resume rather than left running: it is
// showing how long the *recording* is, and a paused stretch is not in it.
let meetingPausedAt = 0;

function toggleMeetingPause() {
  if (!meetingRecorder) return;
  const button = $("meeting-pause");
  if (meetingRecorder.state === "recording") {
    meetingRecorder.pause();
    if (meetingLive.on) holdLiveCaptions(true);
    meetingPausedAt = Date.now();
    stopMeetingTimer();
    setLabel(button, "ph:play Resume");
    setMeetingState("paused");
    $("meeting-status").textContent = "Paused. Resume to keep recording, or stop to transcribe.";
  } else if (meetingRecorder.state === "paused") {
    meetingRecorder.resume();
    if (meetingLive.on) holdLiveCaptions(false);
    // Push the start forward by however long the pause lasted, so the timer
    // keeps reading as the length of the audio rather than of the sitting.
    meetingStartedAt += Date.now() - meetingPausedAt;
    meetingTimerHandle = setInterval(meetingTick, 1000);
    setLabel(button, "ph:pause Pause");
    setMeetingState("recording");
    $("meeting-status").textContent = "Recording.";
  }
}

// An hour of transcript is not a note. In the Notes list it is one enormous
// card nobody can scroll past; as a document it is something you can open,
// edit, extract notes from and export, which is what the rest of this app
// already does well with long text.
async function saveMeetingDocument() {
  const content = $("meeting-transcript").value.trim();
  if (!content) return;
  const status = $("meeting-status");
  const button = $("meeting-save-doc");
  button.disabled = true;
  status.classList.remove("error");
  status.textContent = "Saving…";
  try {
    const title =
      ($("meeting-title")?.value || "").trim() ||
      `Recording: ${whenText()}`;
    const document_ = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title, content }),
    });
    const binned = meetingBinPair("document", document_.id);
    pushUndo("Saved a transcript as a document", binned.undo, binned.redo);
    meetingAcceptOriginal();
    meetingShowSaved(content, "Open the document", () => {
      switchTab("documents");
      openDocument(document_.id);
    }, `Saved “${title}” to your documents.`);
  } catch (error) {
    status.textContent = error.message || "Couldn't save that.";
    status.classList.add("error");
  } finally {
    button.disabled = false;
  }
}

//: The save itself is meetings.js's (`meetingSaveTranscript`, the lazy
//: bundle the meeting sheet is in): a new meeting in the one shape, or the
//: transcript under the Notes of the meeting it was opened from. The title,
//: when one was typed, names the meeting (every list shows a note's first
//: line as its name; without one a recording was named by its first word).
async function saveMeetingNote() {
  const content = $("meeting-transcript").value.trim();
  if (content && $("meeting-overlay").classList.contains("voice-note")) return saveVoiceNoteText(content, ($("meeting-title")?.value || "").trim());
  if (content && (await ensureModule("meetings"))) await meetingSaveTranscript(content, ($("meeting-title")?.value || "").trim(), Number($("meeting-overlay").dataset.target) || null);
}

//: **Recording recovered** (row 5): a tab closed or killed mid-recording left
//: every 10-second slice it sent; the server finished those recordings at
//: this start (`POST /recordings/recover`) and this says so once, with the
//: length kept. Called from `startApp` only when there is something to say,
//: so the lazy bundle is fetched only then.
function noteRecoveredRecordings(rows) {
  for (const row of rows || []) {
    toastAction(`Recording recovered: “${row.title || "Recording"}”, ${meetingClockText(row.duration_ms)} kept.`, "Open", () => openRecordings(row.id));
  }
}

//: A voice note's transcript as a plain note, its title on the first line.
async function saveVoiceNoteText(text, title) {
  const button = $("meeting-save");
  button.disabled = true;
  try {
    const made = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: title ? `${title}\n\n${text}` : text, defer_filing: true }) });
    const binned = meetingBinPair("note", made.id);
    pushUndo("Saved a voice note", binned.undo, binned.redo);
    meetingAcceptOriginal();
    await refreshEntries([made.id]).catch(() => {});
    meetingShowSaved(text, "Open the note", () => flashEntry(made.id));
  } catch (error) {
    meetingSay(error.message || "Couldn't save that.", true);
  } finally {
    button.disabled = false;
  }
}

// --- the recordings library (WORLD_CLASS_PLAN 28.5 row 6) --------------------
//
// After Apple Voice Memos: every kept recording a row with play, a speed from
// 0.5 to 2x, the waveform the recorder drew (its peaks kept with the object),
// the markers pressed while recording, trim and delete. A trim decodes the
// audio in the page, keeps the chosen part as wav (the one container a page
// can write without an encoder: decision 3) and saves it as a new recording
// pointing at its original, which stays until the bin is emptied.

const RECORDING_SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

//: The Library's Recordings sub-tab, or a row on it (`id`): from the palette,
//: the Audio section and "Recording recovered".
async function openRecordings(id = null) {
  await switchTab("library");
  const tab = document.querySelector('#library-subtabs [data-target="library-view-recordings"]');
  //: The sub-tab's press draws the list; pressed again it would not.
  if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
  else await renderRecordings();
  if (!id) return;
  const selector = `#recordings-list [data-recording-id="${Number(id)}"]`;
  for (let i = 0; i < 30 && !document.querySelector(selector); i++) await new Promise((r) => setTimeout(r, 100));
  const row = document.querySelector(selector);
  row?.scrollIntoView({ block: "center" });
  row?.classList.add("flash");
}

let recordingsAsk = 0;

async function renderRecordings() {
  const list = $("recordings-list");
  if (!list) return;
  let body = null;
  const q = ($("recordings-search")?.value || "").trim();
  try {
    //: The server reads names and transcripts (`match` is the line that had
    //: the words); asked again for each answer, so a late reply to an older
    //: query cannot overwrite the list for the newer one.
    const ask = ++recordingsAsk;
    body = await apiJson(`/recordings?limit=500${q ? `&q=${encodeURIComponent(q)}` : ""}`);
    if (ask !== recordingsAsk) return;
  } catch {
    const failed = list.appendChild(document.createElement("li"));
    list.replaceChildren(failed);
    failed.className = "empty-state recordings-empty";
    surfaceFailed(failed, "recordings", renderRecordings);
    return;
  }
  noteRecoveredRecordings(body.recovered);
  const rows = body.recordings;
  list.replaceChildren(...rows.map(recordingRow));
  if (!rows.length) list.appendChild(recordingsEmpty(q ? "match" : "none"));
}

//: **The empty state recipe** (DESIGN.md: icon, title, one sentence, one
//: action), not a grey line: the owner, 2026-10-11, of the bare sentence that
//: was here, "can you add like an icon or smth to this page so it doesnt look
//: so empty??". `kind` is "none", "match" (the search found nothing) or
//: "failed" (the list did not load, the recipe's warn mood).
function recordingsEmpty(kind) {
  const copy = {
    none: ["ph-microphone", "Nothing recorded yet", "Record keeps a voice note here; a meeting's recording lands here too."],
    match: ["ph-magnifying-glass", "No recordings match", "No recording has that in its name or its transcript."],
  }[kind];
  const li = document.createElement("li");
  li.className = "empty-state recordings-empty";
  const icon = document.createElement("span");
  icon.className = "empty-icon";
  icon.setAttribute("aria-hidden", "true");
  const glyph = document.createElement("i");
  glyph.className = `ph ${copy[0]} ph-lead`;
  icon.appendChild(glyph);
  const title = document.createElement("p");
  title.className = "empty-title";
  title.textContent = copy[1];
  const line = document.createElement("p");
  line.textContent = copy[2];
  li.append(icon, title, line);
  //: The one action: what the header's Record does.
  if (kind === "none") {
    const record = document.createElement("button");
    record.type = "button";
    record.className = "ghost small";
    const mic = document.createElement("i");
    mic.className = "ph ph-microphone ph-lead";
    mic.setAttribute("aria-hidden", "true");
    record.append(mic, " Record");
    record.addEventListener("click", () => openVoiceNote());
    li.appendChild(record);
  }
  return li;
}

function recordingFacts(rec) {
  const when = parseServerTime(rec.created_at) || new Date(rec.created_at);
  const facts = [when.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }), meetingClockText(rec.duration_ms), recordingTranscriptState(rec)];
  if (rec.derived === "enhanced") facts.push("enhanced");
  else if (rec.source_id) facts.push("trimmed");
  if (rec.recovered) facts.push("recovered");
  return facts.join(" · ");
}

//: The transcript's state in words, on the card's one line of facts.
function recordingTranscriptState(rec) {
  const run = rec.transcription;
  if (run?.state === "running") return run.progress == null ? "transcribing" : `transcribing ${Math.round(run.progress * 100)}%`;
  if (rec.transcribed) return "transcribed";
  if (run?.state === "failed") return "transcription failed";
  return "not transcribed";
}

//: **One recording, one card** (Brief 96, INBOX 859: "its hard to see the
//: audio progress ... no vertical line ... or a time stamp"). The head is
//: the name and its facts on one line with the actions at its end; under it
//: the player: play, the waveform with a playhead and the marks as ticks,
//: and "1:12 / 4:30"; then the marks as a list, each a time and a comment.
function recordingRow(rec) {
  const li = document.createElement("li");
  li.className = "recording-row";
  li.dataset.recordingId = String(rec.id);
  const audio = document.createElement("audio");
  audio.preload = "none";
  audio.src = `/media/recordings/${rec.id}`;
  const label = rec.title || "this recording";
  const play = smallButton("ph:play", `Play ${label}`, async () => {
    if (!audio.paused) return audio.pause();
    await recordingReady(audio);
    audio.play();
  });
  play.classList.add("recording-play");
  audio.addEventListener("play", () => setLabel(play, "ph:pause"));
  audio.addEventListener("pause", () => setLabel(play, "ph:play"));
  const head = document.createElement("div");
  head.className = "recording-head";
  const name = document.createElement("span");
  name.className = "recording-title";
  name.textContent = rec.title || "Recording";
  name.title = `${rec.title || "Recording"} (${meetingContainerName(rec.mime)})`;
  const facts = document.createElement("span");
  facts.className = "muted recording-facts";
  facts.textContent = recordingFacts(rec);
  const act = document.createElement("div");
  act.className = "recording-act";
  const speed = recordingSpeed(audio);
  act.append(speed, kebabMenu(recordingMenu(rec), `More actions for ${label}`));
  head.append(name, facts, act);
  const player = document.createElement("div");
  player.className = "recording-player";
  const time = document.createElement("span");
  time.className = "muted recording-time";
  const wave = recordingWave(rec, audio, time);
  const mark = smallButton("ph:push-pin", `Mark this moment in ${label} (M)`, () => addRecordingMark(li));
  mark.classList.add("recording-mark-add");
  player.append(play, wave, time, mark);
  const marks = document.createElement("ol");
  marks.className = "recording-marks";
  marks.setAttribute("aria-label", "Marks");
  li.recording = { rec, audio, wave, marks, facts };
  li.append(head, player, marks);
  //: A search that found its words in the talk shows the line and when it was
  //: said; pressing it plays from there.
  if (rec.match) {
    const found = document.createElement("button");
    found.type = "button";
    found.className = "ghost small recording-match";
    found.title = "Play from this line";
    const at = document.createElement("span");
    at.className = "muted";
    at.textContent = meetingClockText(rec.match.start);
    found.append(at, ` ${rec.match.text}`);
    found.addEventListener("click", () => playRecordingFrom(li, rec.match.start));
    li.insertBefore(found, marks);
  }
  if (rec.transcribed) li.append(...recordingTranscript(rec, audio));
  li.append(audio);
  recordingMarksFill(li);
  recordingRunLine(li);
  if (rec.transcription?.state === "running" && !recordingWatches.has(rec.id)) watchRecordingTranscription(rec, {});
  //: M on the card marks the playhead, as M marks the moment while
  //: recording; stopped here because M also opens the app's chords.
  li.addEventListener("keydown", (event) => {
    if (event.key.toLowerCase() !== "m" || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.target.closest("input, textarea, select, [contenteditable]")) return;
    event.preventDefault();
    event.stopPropagation();
    addRecordingMark(li);
  });
  //: After it has a parent: the restyled opener goes beside it.
  enhanceSelect(speed);
  return li;
}


//: **Seekable before the first seek.** A MediaRecorder file carries no
//: length and no index, so Chromium reads its duration as Infinity and seeks
//: only inside what it has buffered (measured: a press at the middle of a
//: 4.7 s take landed at 1.1 s). Asking for a time past the end makes it read
//: the file through once and learn the length; then every seek lands
//: (measured: 4.0 s asked, 4.0 s reached). Done on the first play or seek,
//: so a shelf of recordings costs no request until one is used.
function recordingReady(audio) {
  if (audio.recordingReady) return audio.recordingReady;
  audio.preload = "metadata";
  audio.recordingReady = new Promise((resolve) => {
    let settled = false;
    const done = () => {
      if (settled) return;
      settled = true;
      audio.currentTime = 0;
      resolve();
    };
    audio.addEventListener("loadedmetadata", () => {
      if (Number.isFinite(audio.duration)) return done();
      audio.addEventListener("durationchange", () => Number.isFinite(audio.duration) && done());
      audio.currentTime = 1e101;
    }, { once: true });
    audio.addEventListener("error", done, { once: true });
    audio.load();
  });
  return audio.recordingReady;
}

function recordingSpeed(audio) {
  const select = document.createElement("select");
  select.className = "recording-speed";
  select.setAttribute("aria-label", "Playback speed");
  select.title = "Playback speed";
  for (const speed of RECORDING_SPEEDS) {
    const option = new Option(`${speed}x`, String(speed), speed === 1, speed === 1);
    select.appendChild(option);
  }
  select.addEventListener("change", () => {
    audio.playbackRate = Number(select.value);
    audio.defaultPlaybackRate = audio.playbackRate;
  });
  return select;
}

//: The saved peaks as bars, the played part in the accent, the playhead as
//: a line in the ink, a tick per mark; a press or a drag seeks, the arrows
//: step five seconds. A canvas, as the recorder's own line is.
function recordingWave(rec, audio, time) {
  const canvas = document.createElement("canvas");
  canvas.className = "recording-wave";
  canvas.setAttribute("role", "slider");
  canvas.setAttribute("aria-label", "Position");
  canvas.setAttribute("aria-valuemin", "0");
  canvas.tabIndex = 0;
  const total = () => (Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : rec.duration_ms / 1000);
  const draw = () => {
    const length = total();
    const now = Math.min(audio.currentTime, length || 0);
    recordingPaint(canvas, rec, now / (length || 1));
    const text = `${meetingClockText(now * 1000)} / ${meetingClockText(length * 1000)}`;
    time.textContent = text;
    canvas.setAttribute("aria-valuemax", String(Math.round(length)));
    canvas.setAttribute("aria-valuenow", String(Math.round(now)));
    canvas.setAttribute("aria-valuetext", text);
  };
  const seek = async (fraction) => {
    await recordingReady(audio);
    audio.currentTime = Math.max(0, Math.min(1, fraction)) * total();
    draw();
  };
  const at = (event) => {
    const box = canvas.getBoundingClientRect();
    //: The same inset as the bars (`recordingPaint`), so a press lands where it is drawn.
    const inset = parseFloat(getComputedStyle(canvas).borderTopLeftRadius) || 0;
    return (event.clientX - box.left - inset) / (box.width - 2 * inset || 1);
  };
  //: Press and drag: the pointer is captured so a drag past the end still
  //: seeks, and the playhead follows the finger before the audio has caught up.
  canvas.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    canvas.setPointerCapture?.(event.pointerId);
    canvas.dataset.dragging = "true";
    seek(at(event));
  });
  canvas.addEventListener("pointermove", (event) => {
    if (canvas.dataset.dragging !== "true") return;
    const fraction = Math.max(0, Math.min(1, at(event)));
    recordingPaint(canvas, rec, fraction);
    time.textContent = `${meetingClockText(fraction * total() * 1000)} / ${meetingClockText(total() * 1000)}`;
  });
  const drop = (event) => {
    if (canvas.dataset.dragging !== "true") return;
    delete canvas.dataset.dragging;
    seek(at(event));
  };
  canvas.addEventListener("pointerup", drop);
  canvas.addEventListener("pointercancel", () => delete canvas.dataset.dragging);
  canvas.addEventListener("keydown", (event) => {
    const keys = { ArrowRight: 5, ArrowLeft: -5, Home: -Infinity, End: Infinity };
    if (!(event.key in keys)) return;
    event.preventDefault();
    const step = keys[event.key];
    seek(Number.isFinite(step) ? (audio.currentTime + step) / (total() || 1) : step > 0 ? 1 : 0);
  });
  audio.addEventListener("timeupdate", draw);
  audio.addEventListener("durationchange", draw);
  canvas.recordingSeek = seek;
  canvas.recordingDraw = draw;
  requestAnimationFrame(draw);
  return canvas;
}

function recordingPaint(canvas, rec, played) {
  const box = canvas.getBoundingClientRect();
  if (!box.width) return;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(box.width * ratio);
  canvas.height = Math.round(box.height * ratio);
  const paint = canvas.getContext("2d");
  const style = getComputedStyle(document.documentElement);
  const accent = style.getPropertyValue("--accent").trim() || "#4664f0";
  const rest = style.getPropertyValue("--muted").trim() || "#888";
  const ink = style.getPropertyValue("--text").trim() || "#222";
  const peaks = rec.peaks.length ? rec.peaks : [8];
  //: Bars stay off the rounded ends: inset by the track's own corner.
  const inset = (parseFloat(getComputedStyle(canvas).borderTopLeftRadius) || 0) * ratio;
  const bar = (canvas.width - 2 * inset) / peaks.length;
  const mid = canvas.height / 2;
  //: Bars no thinner than 2 device pixels with a gap, so a long recording
  //: reads as a shape rather than a grey slab.
  const width = Math.max(ratio, bar * 0.6);
  peaks.forEach((peak, i) => {
    const h = Math.max(2 * ratio, (peak / 100) * (canvas.height - 8 * ratio));
    paint.globalAlpha = i / peaks.length < played ? 1 : 0.55;
    paint.fillStyle = i / peaks.length < played ? accent : rest;
    paint.fillRect(inset + i * bar, mid - h / 2, width, h);
  });
  paint.globalAlpha = 1;
  //: A mark is a short tick from the top with a dot, so it never reads as
  //: the playhead, which runs the full height.
  paint.fillStyle = accent;
  for (const mark of rec.marks || []) {
    const x = inset + (mark.at / (rec.duration_ms || 1)) * (canvas.width - 2 * inset);
    paint.fillRect(x - ratio / 2, 0, ratio, canvas.height * 0.35);
    paint.beginPath();
    paint.arc(x, 3 * ratio, 3 * ratio, 0, Math.PI * 2);
    paint.fill();
  }
  const x = Math.max(ratio, Math.min(canvas.width - ratio, inset + played * (canvas.width - 2 * inset)));
  paint.fillStyle = ink;
  paint.fillRect(x - ratio, 0, 2 * ratio, canvas.height);
}

//: The marks under the player: each its time and its comment, pressing it
//: plays from there and lights the transcript line said at that moment.
function recordingMarksFill(li) {
  const { rec, audio, marks } = li.recording;
  marks.replaceChildren(...(rec.marks || []).map((mark, i) => {
    const item = document.createElement("li");
    item.className = "recording-mark";
    const go = document.createElement("button");
    go.type = "button";
    go.className = "recording-mark-go";
    go.title = `Play from ${meetingClockText(mark.at)}`;
    const at = document.createElement("span");
    at.className = "recording-mark-at";
    at.textContent = meetingClockText(mark.at);
    const note = document.createElement("span");
    note.className = mark.note ? "recording-mark-note" : "recording-mark-note muted";
    note.textContent = mark.note || `Mark ${i + 1}`;
    go.append(at, note);
    go.addEventListener("click", () => playRecordingFrom(li, mark.at));
    item.append(go, rowActions([
      { label: mark.note ? "Edit" : "Comment", title: mark.note ? "Change this mark's comment" : "Add a comment to this mark", run: () => editRecordingMark(li, mark) },
      { label: "Remove", title: "Remove this mark", danger: true, run: () => removeRecordingMark(li, mark) },
    ], `Actions for the mark at ${meetingClockText(mark.at)}`));
    return item;
  }));
}

async function playRecordingFrom(li, ms) {
  const { audio } = li.recording;
  await recordingReady(audio);
  audio.currentTime = ms / 1000;
  audio.play();
  recordingShowLine(li, ms);
}

//: A mark links into the transcript: the fold opens on the line being said
//: at that moment.
async function recordingShowLine(li, ms) {
  const toggle = li.querySelector(".recording-transcript-toggle");
  const list = li.querySelector(".recording-transcript");
  if (!toggle || !list) return;
  if (toggle.getAttribute("aria-expanded") !== "true") await toggle.recordingOpen();
  const lines = [...list.querySelectorAll(".recording-line")];
  const line = lines.findLast((button) => Number(button.dataset.start) <= ms) || lines[0];
  if (!line) return;
  lines.forEach((button) => button.classList.toggle("is-now", button === line));
  line.scrollIntoView({ block: "nearest" });
}

//: The marks saved as the server keeps them: a number, or `{at, note}`.
async function saveRecordingMarks(li, marks) {
  const { rec } = li.recording;
  const body = await apiJson(`/recordings/${rec.id}`, {
    method: "PATCH",
    body: JSON.stringify({ markers: marks.map((m) => (m.note ? { at: m.at, note: m.note } : m.at)) }),
  });
  Object.assign(rec, { markers: body.markers, marks: body.marks });
  recordingMarksFill(li);
  li.recording.wave.recordingDraw();
  li.recording.facts.textContent = recordingFacts(rec);
}

//: M or the pin: a mark at the playhead, with a comment if one is typed.
async function addRecordingMark(li) {
  const { rec, audio } = li.recording;
  const at = Math.round(audio.currentTime * 1000);
  const note = await promptDialog(`Comment on the mark at ${meetingClockText(at)} (optional)`, "", { confirmLabel: "Add the mark" });
  if (note === null || note === undefined) return;
  const before = (rec.marks || []).map((m) => ({ ...m }));
  const after = [...before.filter((m) => m.at !== at), { at, note: note.trim() }];
  try {
    await saveRecordingMarks(li, after);
  } catch (error) {
    return toast(error.message || "Couldn't add that mark.", true);
  }
  pushUndo("Added a mark", () => saveRecordingMarks(li, before), () => saveRecordingMarks(li, after));
}

async function editRecordingMark(li, mark) {
  const { rec } = li.recording;
  const note = await promptDialog(`Comment on the mark at ${meetingClockText(mark.at)}`, mark.note, { confirmLabel: "Save" });
  if (note === null || note === undefined || note.trim() === mark.note) return;
  const before = rec.marks.map((m) => ({ ...m }));
  const after = before.map((m) => (m.at === mark.at ? { ...m, note: note.trim() } : m));
  await saveRecordingMarks(li, after).catch((error) => toast(error.message, true));
  pushUndo("Changed a mark", () => saveRecordingMarks(li, before), () => saveRecordingMarks(li, after));
}

async function removeRecordingMark(li, mark) {
  const { rec } = li.recording;
  const before = rec.marks.map((m) => ({ ...m }));
  const after = before.filter((m) => m.at !== mark.at);
  try {
    await saveRecordingMarks(li, after);
  } catch (error) {
    return toast(error.message || "Couldn't remove that mark.", true);
  }
  pushUndo("Removed a mark", () => saveRecordingMarks(li, before), () => saveRecordingMarks(li, after));
  toastAction(`Removed the mark at ${meetingClockText(mark.at)}.`, "Undo", () => saveRecordingMarks(li, before));
}

//: **The transcript under its recording** (28.5 row 7): each line a button
//: that plays from its moment, the line being spoken marked, as Otter's
//: are. Read when first opened: an hour is about 700 lines, and the shelf
//: lists every recording.
function recordingTranscript(rec, audio) {
  const list = document.createElement("ol");
  list.className = "recording-transcript hidden";
  const flip = async (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    list.classList.toggle("hidden", !open);
    if (open && !list.childElementCount) await recordingTranscriptFill(rec, audio, list);
  };
  const toggle = smallButton("ph:caret-down Transcript", "Show the transcript; a line plays from its moment", () => flip(toggle.getAttribute("aria-expanded") !== "true"));
  //: A mark opens it on its line (`recordingShowLine`).
  toggle.recordingOpen = () => flip(true);
  toggle.classList.add("recording-transcript-toggle");
  toggle.setAttribute("aria-expanded", "false");
  return [toggle, list];
}

async function recordingTranscriptFill(rec, audio, list) {
  let body = null;
  try {
    body = await apiJson(`/recordings/${rec.id}/transcript`);
  } catch (error) {
    //: A line inside the card, the small-panel recipe (`.empty-line`).
    const line = document.createElement("li");
    line.className = "muted empty-line";
    line.textContent = error.message || "Couldn't read the transcript.";
    list.replaceChildren(line);
    return;
  }
  //: **Copying lines** (INBOX 1300 C40, the owner: "no way to copy
  //: individual or multiple lines of the transcript"). A line's own copy
  //: button shows on hover and focus; Shift-click on a line picks the run
  //: from the last one clicked (Ctrl or Cmd-click adds one) and a plain click
  //: still plays; the row's ⋯ copies the picked lines or all of them, with
  //: the times or without. The keys work as the clicks do: Shift+Enter on a
  //: focused line is a Shift-click.
  const segs = body.segments;
  const picked = new Set();
  let anchor = -1;
  const lineText = (seg, times) =>
    `${times ? `[${meetingClockText(seg.start)}] ` : ""}${seg.speaker ? `${seg.speaker}: ` : ""}${seg.text}`;
  const copyLines = (indexes, times, button) => copyToClipboard(indexes.map((i) => lineText(segs[i], times)).join("\n"), button);
  const tools = document.createElement("li");
  tools.className = "recording-transcript-tools";
  const note = document.createElement("span");
  note.className = "muted";
  const buttons = [];
  const sync = () => {
    note.textContent = picked.size
      ? `${picked.size} line${picked.size === 1 ? "" : "s"} picked`
      : "Shift-click picks a run of lines to copy";
    buttons.forEach((button, i) => {
      const on = picked.has(i);
      button.classList.toggle("is-picked", on);
      button.setAttribute("aria-pressed", String(on));
    });
  };
  const chosen = () => [...picked].sort((a, b) => a - b);
  const copyPicked = (times) => (picked.size ? copyLines(chosen(), times) : toast("Pick lines first: Shift-click a line, then another."));
  const all = segs.map((_, i) => i);
  const menu = kebabMenu(
    [
      makeMenuItem("ph:copy Copy picked lines", "Copy the lines you picked, text only", () => copyPicked(false)),
      makeMenuItem("ph:clock Copy picked lines with times", "Copy the lines you picked, each starting with its time", () => copyPicked(true)),
      makeMenuItem("ph:copy Copy all", "Copy the whole transcript, text only", () => copyLines(all, false)),
      makeMenuItem("ph:clock Copy all with times", "Copy the whole transcript, each line starting with its time", () => copyLines(all, true)),
      makeMenuItem("ph:x Clear the picked lines", "Let go of the lines you picked", () => (picked.clear(), sync())),
    ],
    "Copy the transcript"
  );
  tools.append(note, menu);
  const lines = segs.map((seg, i) => {
    const li = document.createElement("li");
    li.className = "recording-line-row";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "recording-line";
    button.dataset.start = String(seg.start);
    button.setAttribute("aria-pressed", "false");
    const at = document.createElement("span");
    at.className = "muted recording-line-at";
    at.textContent = meetingClockText(seg.start);
    const said = document.createElement("span");
    said.textContent = seg.text;
    //: A speaker only when the model named the turns (row 11).
    if (seg.speaker) {
      const who = document.createElement("span");
      who.className = "recording-line-who";
      who.textContent = seg.speaker;
      button.append(at, who, said);
    } else button.append(at, said);
    button.addEventListener("click", async (event) => {
      if (event.shiftKey || event.ctrlKey || event.metaKey) {
        if (event.shiftKey && anchor >= 0) {
          for (let n = Math.min(anchor, i); n <= Math.max(anchor, i); n += 1) picked.add(n);
        } else if (picked.has(i)) picked.delete(i);
        else picked.add(i);
        anchor = i;
        return sync();
      }
      anchor = i;
      await recordingReady(audio);
      audio.currentTime = seg.start / 1000;
      audio.play();
    });
    buttons.push(button);
    const copy = smallButton("ph:copy", "Copy this line", () => copyLines([i], false, copy));
    copy.classList.add("recording-line-copy");
    copy.setAttribute("aria-label", `Copy the line at ${meetingClockText(seg.start)}`);
    li.append(button, copy);
    return li;
  });
  list.replaceChildren(tools, ...lines);
  sync();
  audio.addEventListener("timeupdate", () => recordingTranscriptNow(list, body.segments, audio.currentTime * 1000));
}

function recordingTranscriptNow(list, segments, ms) {
  const now = segments.findLastIndex((seg) => seg.start <= ms);
  list.querySelectorAll(".recording-line").forEach((button, i) => {
    button.classList.toggle("is-now", i === now);
    if (i === now) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  });
}

//: The file extension for a container name that is not one (an MP4 audio file
//: is .m4a); webm, ogg and wav are their own.
const RECORDING_EXTENSIONS = { mp4: "m4a" };

function recordingMenu(rec) {
  const items = [
    makeMenuItem("ph:pencil-simple Rename", "Give this recording a name", () => renameRecording(rec)),
    makeMenuItem("ph:download-simple Download audio", "Save the recording as an audio file", () => downloadFromApi(`/media/recordings/${rec.id}`, `${(rec.title || "recording").replace(/[^A-Za-z0-9._ -]/g, "_")}.${RECORDING_EXTENSIONS[meetingContainerName(rec.mime)] || meetingContainerName(rec.mime)}`)),
    makeMenuItem("ph:scissors Trim", "Keep part of it as a new recording; the original stays until the bin is emptied", () => openRecordingTrim(rec)),
  ];
  //: Always offered. It used to appear only when `voiceStatus` said the add-on
  //: was there, and that is fetched by the recorder alone: a library opened
  //: first had no Transcribe even with the add-on installed, and one without
  //: the add-on had no row to say why. Pressed, it asks once and either runs
  //: or says what is missing.
  items.push(makeMenuItem("ph:text-aa Transcribe", "Transcribe it on this computer", async () => {
    if (voiceStatus === null) voiceStatus = await apiJson("/voice/status").catch(() => ({ available: false }));
    if (!voiceStatus.available) return toast(voiceStatus.hint || "Transcribing needs the Voice notes add-on, in Settings, Packages.", "info");
    transcribeRecording(rec);
  }));
  if (rec.transcribed) {
    const name = (rec.title || "recording").replace(/[^A-Za-z0-9._ -]/g, "_");
    //: Row 11: offered only with a model on; with none, no label is shown.
    if (!aiIsOff()) items.push(makeMenuItem("ph:users-three Name the speakers", "Let the local AI name who speaks each turn, from what is said", () => nameRecordingSpeakers(rec)));
    items.push(makeMenuItem("ph:user-switch Rename a speaker", "Change a speaker's name everywhere in this transcript", () => renameRecordingSpeaker(rec)));
    items.push(
      makeMenuItem("ph:closed-captioning Subtitles (SRT)", "Download the transcript with its times as an SRT file", () => downloadFromApi(`/recordings/${rec.id}/transcript.srt`, `${name}.srt`)),
      makeMenuItem("ph:closed-captioning Subtitles (VTT)", "Download the transcript with its times as a WebVTT file", () => downloadFromApi(`/recordings/${rec.id}/transcript.vtt`, `${name}.vtt`))
    );
  }
  items.push(makeMenuItem("ph:trash Delete", "Put it in the bin", () => binRecording(rec)));
  return items;
}

//: Ledger 1514: speaker names are the person's to correct. Which speaker
//: first (only asked when there are several), then the new name; blank drops
//: the label. Undo puts the old name back.
async function renameRecordingSpeaker(rec) {
  try {
    const body = await apiJson(`/recordings/${rec.id}/transcript`);
    const names = [...new Set(body.segments.map((seg) => seg.speaker).filter(Boolean))];
    if (!names.length) {
      toast("This transcript has no speaker names yet. Name the speakers first.", "info");
      return;
    }
    let from = names[0];
    if (names.length > 1) {
      const picked = await promptDialog(`Which speaker? ${names.join(", ")}`, names[0], { confirmLabel: "Next" });
      if (picked === null || picked === undefined || !names.includes(picked.trim())) return;
      from = picked.trim();
    }
    const to = await promptDialog(`New name for ${from}`, from, { confirmLabel: "Rename" });
    if (to === null || to === undefined || to.trim() === from) return;
    const put = (a, b) => apiJson(`/recordings/${rec.id}/speakers`, { method: "PUT", body: JSON.stringify({ from_name: a, to_name: b }) }).then(renderRecordings);
    await put(from, to.trim());
    pushUndo("Renamed a speaker", () => put(to.trim() || from, from), () => put(from, to.trim()));
  } catch (error) {
    toast(error.message || "Couldn't rename that speaker.", true);
  }
}

async function nameRecordingSpeakers(rec) {
  try {
    const body = await apiJson(`/recordings/${rec.id}/speakers`, { method: "POST" });
    await renderRecordings();
    toast(body.speakers ? "Named the speakers; open Transcript to see them." : "The local AI could not tell the speakers apart.", "info");
  } catch (error) {
    toast(error.message || "Couldn't name the speakers.", true);
  }
}

async function renameRecording(rec) {
  const title = await promptDialog("Name this recording", rec.title || "", { confirmLabel: "Rename" });
  if (title === null || title === undefined || title.trim() === (rec.title || "")) return;
  const before = rec.title || "";
  const put = (value) => apiJson(`/recordings/${rec.id}`, { method: "PATCH", body: JSON.stringify({ title: value }) }).then(renderRecordings);
  await put(title.trim()).catch((error) => toast(error.message, true));
  pushUndo("Renamed a recording", () => put(before), () => put(title.trim()));
}

async function binRecording(rec) {
  const undo = () => apiJson(`/recordings/${rec.id}/restore`, { method: "POST" }).then(renderRecordings);
  const redo = () => apiJson(`/recordings/${rec.id}`, { method: "DELETE" }).then(renderRecordings);
  try {
    await redo();
  } catch (error) {
    toast(error.message || "Couldn't delete that recording.", true);
    return;
  }
  pushUndo("Deleted a recording", undo, redo);
  toastAction(`“${rec.title || "Recording"}” is in the bin.`, "Undo", undo);
}

//: The ⋯'s Transcribe: a background run (V1), its progress on the card and
//: in the running panel; when it ends the transcript is saved as a note and
//: a notification says so, with Open.
async function transcribeRecording(rec) {
  try {
    await startRecordingTranscription(rec, {
      done: async () => {
        const body = await apiJson(`/recordings/${rec.id}/transcript`).catch(() => ({ segments: [] }));
        const text = body.segments.map((seg) => seg.text).join(" ").trim();
        if (!text) return toast(`Nothing was heard in “${rec.title || "Recording"}”.`, "info");
        const made = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `${rec.title || "Recording"}\n\n${text}`, defer_filing: true }) });
        const binned = meetingBinPair("note", made.id);
        pushUndo("Saved a transcript as a note", binned.undo, binned.redo);
        await refreshEntries([made.id]).catch(() => {});
      },
    });
    toast("Transcribing in the background; you will be told when it is done.", "info");
  } catch (error) {
    toast(error.message || "Couldn't transcribe that recording.", true);
  }
}

// --- background transcription (UI_MODERNISATION V1, INBOX 828) ---------------
//
// The run is the server's (`POST /recordings/{id}/transcribe/start`); this
// page watches it, once per recording, from the moment it starts until it
// ends, whatever is on screen. Every card of that recording shows its
// progress and a Stop; the ending is a notification with Open, so it is
// found after the dialog, the tab or the panel that started it has gone.
// A reload loses the watch, not the run: the card still reads its state.

const RECORDING_WATCH_MS = 1500;
const recordingWatches = new Map();

async function startRecordingTranscription(rec, hooks = {}) {
  const body = await apiJson(`/recordings/${rec.id}/transcribe/start`, { method: "POST" });
  watchRecordingTranscription(rec, hooks);
  recordingCardsRun(rec.id, body.transcription);
  return body;
}

async function stopRecordingTranscription(id) {
  try {
    const body = await apiJson(`/recordings/${id}/transcribe/stop`, { method: "POST" });
    if (!body.stopped) toast(body.detail, "info");
  } catch (error) {
    toast(error.message || "Couldn't stop that.", true);
  }
}

function watchRecordingTranscription(rec, hooks) {
  clearTimeout(recordingWatches.get(rec.id));
  const poll = async () => {
    const now = await apiJson(`/recordings/${rec.id}`, { silent: true }).catch(() => null);
    const run = now?.transcription;
    if (!run || run.state === "running") {
      if (run) {
        hooks.progress?.(run);
        recordingCardsRun(rec.id, run);
      }
      recordingWatches.set(rec.id, setTimeout(poll, RECORDING_WATCH_MS));
      return;
    }
    recordingWatches.delete(rec.id);
    await recordingTranscriptionEnded(now, run, hooks);
  };
  recordingWatches.set(rec.id, setTimeout(poll, RECORDING_WATCH_MS));
}

async function recordingTranscriptionEnded(rec, run, hooks) {
  const name = rec.title || "Recording";
  for (const li of document.querySelectorAll(`#recordings-list [data-recording-id="${Number(rec.id)}"]`)) {
    if (li.recording) li.recording.rec.transcribed = rec.transcribed;
  }
  recordingCardsRun(rec.id, run);
  const here = hooks.here?.() || false;
  if (run.state === "done") {
    await hooks.done?.(run);
    if (!here) {
      recordNotification({ kind: "task", title: `Transcript ready: “${name}”`, detail: `${run.words} words`, key: `transcription:${rec.id}:${Date.now()}`, action: { open: "recording", id: rec.id } });
      toastAction(`Transcript ready: “${name}”.`, "Open", () => openRecordings(rec.id));
    }
  } else if (run.state === "failed") {
    hooks.ended?.(run);
    recordNotification({ kind: "error", title: `Couldn't transcribe “${name}”`, detail: run.error, key: `transcription:${rec.id}:${Date.now()}`, action: { open: "recording", id: rec.id } });
    if (!here) toastAction(`Couldn't transcribe “${name}”: ${run.error}`, "Open", () => openRecordings(rec.id));
  } else {
    hooks.ended?.(run);
    if (!here) toast(`Stopped transcribing “${name}”.`, "info");
  }
  if (!$("library-view-recordings")?.classList.contains("hidden")) renderRecordings();
}

//: Every card of the recording, told how its run is going: the facts line,
//: and a bar with Stop while it runs.
function recordingCardsRun(id, run) {
  for (const li of document.querySelectorAll(`#recordings-list [data-recording-id="${Number(id)}"]`)) {
    if (!li.recording) continue;
    li.recording.rec.transcription = run;
    li.recording.facts.textContent = recordingFacts(li.recording.rec);
    recordingRunLine(li);
  }
}

function recordingRunLine(li) {
  const { rec } = li.recording;
  const running = rec.transcription?.state === "running";
  let line = li.querySelector(".recording-run");
  if (!running) return line?.remove();
  if (!line) {
    line = document.createElement("div");
    line.className = "recording-run";
    const bar = document.createElement("progress");
    bar.className = "recording-run-bar";
    bar.setAttribute("aria-label", `Transcribing ${rec.title || "this recording"}`);
    const stop = smallButton("ph:stop Stop", "Stop transcribing; nothing is kept", () => stopRecordingTranscription(rec.id));
    stop.classList.add("quiet");
    line.append(bar, stop);
    li.querySelector(".recording-player").after(line);
  }
  const bar = line.querySelector("progress");
  if (rec.transcription.progress == null) bar.removeAttribute("value");
  else {
    bar.max = 1;
    bar.value = rec.transcription.progress;
  }
}

//: The page's memory for a trim, measured on a decoded hour (about 700 MB).
const RECORDING_TRIM_MB_PER_MINUTE = 12;
const RECORDING_TRIM_HEAVY_MINUTES = 20;

//: **Trim**: a sheet with the waveform and the two ends; Save writes the
//: part kept as a new recording.
function openRecordingTrim(rec) {
  openSheet({
    label: "Trim the recording",
    sub: `${rec.title || "Recording"} · ${meetingClockText(rec.duration_ms)}`,
    name: "recording-trim",
    build: (card, close) => {
      card.classList.add("recording-trim");
      const total = rec.duration_ms;
      const start = recordingTrimField("Start", 0, total, "recording-trim-start");
      const end = recordingTrimField("End", total, total, "recording-trim-end");
      const kept = document.createElement("p");
      kept.className = "status";
      kept.setAttribute("role", "status");
      //: **Said before it is spent** (libr-1011 row 1219): a trim decodes the
      //: whole take in this tab (about 12 MB a minute), so a long one says so
      //: here, and a short one stays quiet. The cut itself cannot be made on
      //: the server until the app ships a container writer.
      const minutes = Math.round(total / 60000);
      const heavy = [];
      if (minutes >= RECORDING_TRIM_HEAVY_MINUTES) {
        const note = document.createElement("p");
        note.className = "muted recording-trim-weight";
        note.textContent = `Trimming opens the whole recording in this tab: about ${minutes * RECORDING_TRIM_MB_PER_MINUTE} MB of memory for ${minutes} minutes.`;
        heavy.push(note);
      }
      const sync = () => {
        const a = Number(start.input.value);
        const b = Number(end.input.value);
        kept.textContent = b > a ? `Keeps ${meetingClockText(a)} to ${meetingClockText(b)} (${meetingClockText(b - a)}) as a new recording.` : "The end must come after the start.";
        save.disabled = !(b > a) || (a === 0 && b === total);
      };
      const bar = document.createElement("div");
      bar.className = "row right space-dialog-actions";
      const cancel = smallButton("Cancel", "Keep the recording as it is", close);
      const save = smallButton("ph:scissors Save the trim", "Save the part kept as a new recording", async () => {
        save.disabled = true;
        setLabel(kept, "ph:spin Trimming…");
        try {
          const made = await trimRecording(rec, Number(start.input.value), Number(end.input.value));
          close();
          await renderRecordings();
          toastAction(`Saved “${made.title}”. The original is kept.`, "Show", () => openRecordings(made.id));
        } catch (error) {
          kept.textContent = error.message || "Couldn't trim that recording.";
          kept.classList.add("error");
          save.disabled = false;
        }
      }, false);
      save.id = "recording-trim-save";
      for (const field of [start, end]) field.input.addEventListener("input", sync);
      bar.append(cancel, save);
      card.append(start.row, end.row, kept, ...heavy, bar);
      sync();
    },
  });
}

function recordingTrimField(label, value, total, id) {
  const input = document.createElement("input");
  input.type = "range";
  input.min = "0";
  input.max = String(total);
  input.step = "100";
  input.value = String(value);
  const out = document.createElement("output");
  out.className = "recording-trim-at";
  out.htmlFor = id;
  const show = () => {
    out.textContent = meetingClockText(Number(input.value));
  };
  input.addEventListener("input", show);
  show();
  const row = meetingFormRow(label, input, id);
  row.appendChild(out);
  return { row, input };
}

async function trimRecording(rec, startMs, endMs) {
  const buffer = await (await api(`/media/recordings/${rec.id}`)).arrayBuffer();
  const context = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 1, 44100);
  const decoded = await context.decodeAudioData(buffer);
  const wav = recordingWav(decoded, startMs / 1000, endMs / 1000);
  const made = await apiJson("/recordings", {
    method: "POST",
    body: JSON.stringify({ title: `${rec.title || "Recording"} (trimmed)`, mime: "audio/wav", source_id: rec.id, entry_id: rec.entry_id, derived: "trim" }),
  });
  const form = new FormData();
  form.append("file", wav, "trim.wav");
  form.append("duration_ms", String(endMs - startMs));
  await api.upload(`/recordings/${made.id}/chunk`, form);
  const span = rec.duration_ms || 1;
  const peaks = rec.peaks.slice(Math.floor((startMs / span) * rec.peaks.length), Math.ceil((endMs / span) * rec.peaks.length));
  const markers = (rec.marks || []).filter((m) => m.at >= startMs && m.at <= endMs).map((m) => (m.note ? { at: m.at - startMs, note: m.note } : m.at - startMs));
  const done = await apiJson(`/recordings/${made.id}/finish`, { method: "POST", body: JSON.stringify({ duration_ms: endMs - startMs, peaks, markers }) });
  const binned = { undo: () => apiJson(`/recordings/${made.id}`, { method: "DELETE" }).then(renderRecordings), redo: () => apiJson(`/recordings/${made.id}/restore`, { method: "POST" }).then(renderRecordings) };
  pushUndo("Trimmed a recording", binned.undo, binned.redo);
  return done;
}

//: The decoded audio from `from` to `to` seconds, mixed to one channel, as
//: 16-bit PCM wav: a header of 44 bytes and the samples.
function recordingWav(decoded, from, to) {
  const rate = decoded.sampleRate;
  const first = Math.max(0, Math.floor(from * rate));
  const last = Math.min(decoded.length, Math.ceil(to * rate));
  const count = Math.max(0, last - first);
  const channels = [...Array(decoded.numberOfChannels).keys()].map((c) => decoded.getChannelData(c));
  const view = new DataView(new ArrayBuffer(44 + count * 2));
  const text = (at, word) => [...word].forEach((ch, i) => view.setUint8(at + i, ch.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + count * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, count * 2, true);
  for (let i = 0; i < count; i++) {
    let sum = 0;
    for (const data of channels) sum += data[first + i];
    const sample = Math.max(-1, Math.min(1, sum / channels.length));
    view.setInt16(44 + i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

//: **A marker while recording** (row 6): the button or M, a moment in the
//: object (`markers`, milliseconds into the audio).
function addMeetingMarker() {
  if (!meetingRecorder || meetingRecorder.state === "inactive") return;
  const at = Math.round(meetingElapsedMs());
  meetingTake.markers.push(at);
  meetingSay(`Marker ${meetingTake.markers.length} at ${meetingClockText(at)}.`);
}

//: The Recordings shelf's Record and search: the shelf is drawn by this
//: bundle, so it is in before either can be pressed (and app.js's boot
//: budget carries no stand-in for them).
$("recordings-record")?.addEventListener("click", () => openVoiceNote());

//: **Live captions from where a person looks for them** (V6): the voice
//: note's Live captions and the Recordings bar's Captions. The dialog makes
//: way for the floating bar; a recording in hand already writes its words.
function openLiveCaptionsFrom() {
  if (meetingRecorder) return toast("This recording already writes its words in the dialog as you speak.", "info");
  if (!$("meeting-overlay").classList.contains("hidden")) closeMeetingRecorder();
  ensureModule("captions").then((ok) => ok && startLiveCaptions());
}
$("meeting-captions")?.addEventListener("click", openLiveCaptionsFrom);
$("meeting-done-open")?.addEventListener("click", () => {
  const open = $("meeting-done").openSaved;
  closeMeetingRecorder();
  open?.();
});
$("meeting-done-again")?.addEventListener("click", () => {
  resetMeetingUI();
  $("meeting-record").focus();
});
$("recordings-captions")?.addEventListener("click", openLiveCaptionsFrom);
$("meeting-copy")?.addEventListener("click", (event) =>
  copyToClipboard($("meeting-transcript").value, event.currentTarget)
);
$("meeting-transcript").addEventListener("input", () => autoGrow($("meeting-transcript")));
let recordingsSearchTimer = 0;
$("recordings-search")?.addEventListener("input", () => {
  clearTimeout(recordingsSearchTimer);
  recordingsSearchTimer = setTimeout(renderRecordings, 200);
});
$("meeting-save-doc")?.addEventListener("click", saveMeetingDocument);
$("meeting-pause")?.addEventListener("click", toggleMeetingPause);

//: Wired when this bundle loads: the Marker button shows only while
//: recording, which only this bundle starts. M anywhere in the recorder but
//: its name field is the same; stopped here, because M is also the first key
//: of the app's chords (m then s), and while recording it is the marker.
$("meeting-marker")?.addEventListener("click", addMeetingMarker);
$("meeting-discard-take")?.addEventListener("click", discardMeetingTake);
$("meeting-stop-transcribe")?.addEventListener("click", stopMeetingTranscription);
//: The dock (V1) is in the page from boot but shows only once this bundle
//: has started a recording, so its handlers are this bundle's.
$("recording-dock-open")?.addEventListener("click", showMeetingRecorder);
$("recording-dock-pause")?.addEventListener("click", () => {
  toggleMeetingPause();
  syncRecordingDock();
});
$("recording-dock-stop")?.addEventListener("click", () => toggleMeetingRecording());
$("meeting-overlay")?.addEventListener("keydown", (event) => {
  if (event.key.toLowerCase() !== "m" || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest("input, textarea") || $("meeting-marker").classList.contains("hidden")) return;
  event.preventDefault();
  event.stopPropagation();
  addMeetingMarker();
});

//: The recorder overlay's buttons (§17), wired here since the overlay opens
//: only once this file is in (they were in settings-wiring.js, at boot, until
//: the boot scripts' gzip ratchet needed the bytes).
$("meeting-close").addEventListener("click", closeMeetingRecorder);
wireBackdropClose($("meeting-overlay"), () => closeMeetingRecorder());
$("meeting-record").addEventListener("click", toggleMeetingRecording);
$("meeting-save").addEventListener("click", saveMeetingNote);
$("meeting-discard").addEventListener("click", resetMeetingUI);

// --- the microphone, chosen and tested (UI_MODERNISATION V2, INBOX 828) -------
//
// One set of controls, drawn into the recorder's Microphone fold and into
// Settings, General, Microphone: which input, the browser's noise
// suppression, echo cancellation and automatic gain (each a switch, on by
// default, kept on this computer and read by `micAudioConstraints`), a live
// level and a three-second test that plays back what it heard. A device
// list carries names only once the browser has been allowed the microphone,
// so the test also fills them in.

const MIC_SWITCHES = [
  ["micNoise", "Noise suppression", "Quietens steady background noise: fans, hum, traffic"],
  ["micEcho", "Echo cancellation", "Removes the speakers' sound coming back into the microphone"],
  ["micGain", "Automatic gain", "Evens out loud and quiet speech"],
  ["micEnhance", "Enhance on save", "Cuts low rumble and evens the loudness of the kept audio, on this machine; the original is kept until the transcript is saved"],
  //: Off unless chosen, because it stores speech: the fourth element is the default (libr-1011 row 1226).
  ["captionsKeepAudio", "Keep the audio of live captions", "Stop saves the captions as a note and the audio as a recording, with the lines as its transcript; off keeps only the note", false],
];
const MIC_TEST_MS = 3000;

function micControlsInto(host) {
  host.replaceChildren();
  host.classList.add("mic-controls");
  const id = `mic-device-${host.id || Math.random().toString(36).slice(2, 7)}`;
  const select = document.createElement("select");
  select.id = id;
  select.className = "mic-device";
  select.setAttribute("aria-label", "Microphone");
  select.addEventListener("change", () => {
    prefs.set("micDevice", select.value);
    syncMicSelects(select);
  });
  const deviceRow = document.createElement("div");
  deviceRow.className = "row space-between setting-row";
  const label = document.createElement("label");
  label.htmlFor = id;
  label.textContent = "Microphone";
  deviceRow.append(label, select);
  host.appendChild(deviceRow);
  for (const [key, name, hint, fallback = true] of MIC_SWITCHES) {
    const row = document.createElement("label");
    row.className = "check-row";
    row.title = hint;
    const box = document.createElement("input");
    box.type = "checkbox";
    box.dataset.micPref = key;
    box.checked = prefs.bool(key, fallback);
    box.addEventListener("change", () => {
      prefs.set(key, box.checked ? "1" : "0");
      document.querySelectorAll(`input[data-mic-pref="${key}"]`).forEach((other) => (other.checked = box.checked));
    });
    const words = document.createElement("span");
    words.textContent = name;
    row.append(box, words);
    host.appendChild(row);
  }
  const test = document.createElement("div");
  test.className = "mic-test";
  const level = document.createElement("div");
  level.className = "mic-level";
  level.setAttribute("role", "meter");
  level.setAttribute("aria-label", "Microphone level");
  level.setAttribute("aria-valuemin", "0");
  level.setAttribute("aria-valuemax", "100");
  level.setAttribute("aria-valuenow", "0");
  const fill = document.createElement("span");
  fill.className = "mic-level-fill";
  level.appendChild(fill);
  const status = document.createElement("p");
  status.className = "muted mic-test-status";
  status.setAttribute("role", "status");
  status.textContent = "Test records three seconds and plays them back.";
  const button = smallButton("ph:microphone Test", "Record three seconds with these settings and play them back", () => testMicrophone(level, status, button));
  button.classList.add("mic-test-button");
  test.append(button, level);
  host.append(test, status);
  enhanceSelect(select);
  fillMicDevices(select);
}

async function fillMicDevices(select) {
  const chosen = prefs.get("micDevice", "");
  const all = (await navigator.mediaDevices?.enumerateDevices?.().catch(() => [])) || [];
  const inputs = all.filter((d) => d.kind === "audioinput" && d.deviceId !== "default" && d.deviceId !== "communications");
  const options = [new Option("The system default", "", !chosen, !chosen)];
  inputs.forEach((d, i) => options.push(new Option(d.label || `Microphone ${i + 1}`, d.deviceId, false, d.deviceId === chosen)));
  //: Remembered but not plugged in now: kept, said so, still chosen.
  if (chosen && !inputs.some((d) => d.deviceId === chosen)) options.push(new Option("The last microphone chosen (not connected)", chosen, true, true));
  select.replaceChildren(...options);
}

//: Every other copy of the controls follows a change made in one.
function syncMicSelects(from) {
  document.querySelectorAll("select.mic-device").forEach((other) => {
    if (other === from) return;
    other.value = from.value;
  });
}

//: Three seconds through the chosen settings: the level moves while it
//: listens, then it plays back. Names the device it used.
async function testMicrophone(level, status, button) {
  let stream = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraints() });
  } catch {
    status.textContent = "Microphone access was blocked; allow it in your browser.";
    return;
  }
  button.disabled = true;
  const used = stream.getAudioTracks()[0]?.label || "the microphone";
  document.querySelectorAll("select.mic-device").forEach(fillMicDevices);
  const stopLevel = micLevelInto(stream, level);
  const chunks = [];
  const recorder = new MediaRecorder(stream);
  recorder.addEventListener("dataavailable", (e) => e.data.size && chunks.push(e.data));
  const stopped = new Promise((resolve) => recorder.addEventListener("stop", resolve, { once: true }));
  recorder.start();
  status.textContent = `Listening on ${used}: say something…`;
  await new Promise((r) => setTimeout(r, MIC_TEST_MS));
  recorder.stop();
  await stopped;
  stopLevel();
  stream.getTracks().forEach((t) => t.stop());
  const peak = Number(level.dataset.peak || 0);
  const audio = document.createElement("audio");
  audio.src = URL.createObjectURL(new Blob(chunks, { type: recorder.mimeType }));
  status.textContent = peak < 4 ? `Heard almost nothing on ${used}. Check it is not muted, or choose another microphone.` : `Playing back what ${used} heard.`;
  audio.addEventListener("ended", () => {
    URL.revokeObjectURL(audio.src);
    button.disabled = false;
    if (peak >= 4) status.textContent = `${used} works. Its loudest moment reached ${peak}%.`;
  });
  audio.play().catch(() => (button.disabled = false));
}

//: The live level as a bar (the evidence track's recipe: a track and a fill
//: whose width is set): RMS, square-rooted as the recorder's line is so
//: ordinary speech sits mid-bar. With reduced motion it steps four times a
//: second rather than every frame.
function micLevelInto(stream, level) {
  let ctx = null;
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
  } catch {
    return () => {};
  }
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const samples = new Uint8Array(analyser.fftSize);
  const fill = level.querySelector(".mic-level-fill");
  const still = reducedMotionWanted();
  level.dataset.peak = "0";
  let stopped = false;
  let last = 0;
  const tick = (now) => {
    if (stopped) return;
    if (!still || now - last > 250) {
      last = now;
      analyser.getByteTimeDomainData(samples);
      let sum = 0;
      for (const v of samples) sum += ((v - 128) / 128) ** 2;
      const pct = Math.round(Math.min(1, Math.sqrt(Math.sqrt(sum / samples.length)) * 1.6) * 100);
      fill.style.width = `${pct}%`;
      level.setAttribute("aria-valuenow", String(pct));
      level.dataset.peak = String(Math.max(pct, Number(level.dataset.peak)));
    }
    requestAnimationFrame(tick);
  };
  ctx.resume().then(() => requestAnimationFrame(tick), () => requestAnimationFrame(tick));
  return () => {
    stopped = true;
    fill.style.width = "0%";
    level.setAttribute("aria-valuenow", "0");
    ctx.close().catch(() => {});
  };
}

//: The recorder's Microphone fold, drawn when first opened; its summary
//: names the input in use, so a wrong microphone is seen before recording.
async function nameMeetingMic() {
  const chosen = prefs.get("micDevice", "");
  let name = "the system default";
  if (chosen) {
    const all = (await navigator.mediaDevices?.enumerateDevices?.().catch(() => [])) || [];
    name = all.find((d) => d.deviceId === chosen)?.label || "the one chosen";
  }
  if ($("meeting-mic-name")) $("meeting-mic-name").textContent = `Microphone: ${name}`;
}

$("meeting-mic")?.addEventListener("toggle", () => {
  const host = $("meeting-mic-controls");
  if ($("meeting-mic").open && !host.childElementCount) micControlsInto(host);
});
$("meeting-mic")?.addEventListener("change", (event) => {
  if (event.target.matches("select.mic-device")) nameMeetingMic();
});
