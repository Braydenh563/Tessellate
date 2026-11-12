// confirmed-patterns.js: a confirmed pattern's menu (CHAT_PLAN B9), lazy for
// the boot gzip budget: its three callers (settings-controls.js, tidy.js,
// dash-day.js) are lazy themselves and `lazyScript` it before drawing one.

//: **A confirmed pattern's menu** (the owner: "also is there a way to edit or
//: managed confirmed patterns??"): Edit, Not right and Remove, one set for
//: Settings' What it remembers (`rowActions`) and the Patterns line in Tidy
//: and on the dashboard (`kebabMenu`). `about` is a listed item (`id`,
//: `sentence`, `subject`) or a Patterns row (`confirmed_id`, `text`,
//: `slots.subject`). Remove and Not right go on the undo stack.
(() => {
  function confirmedPatternItems(about, onChange) {
    const at = `/insights/confirmed/${about.confirmed_id ?? about.id}`;
    const said = about.sentence ?? String(about.text || "").replace(/, as you told me on [^,]*$/, "");
    const subject = about.subject ?? (about.confirmed_subject || about.slots?.subject || "");
    //: Wherever the change was made, the dashboard's Patterns line is drawn
    //: again too (it is in the DOM when hidden; it only reads).
    const changed = () => {
      onChange?.();
      renderDashSubmessage().catch(() => {});
    };
    const call = (path, method, body) => apiJson(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }).finally(changed);
    const fail = (error) => toast(error.message, true);
    const undoWords = { sentence: "Edited a confirmed pattern", subject: "Changed what a pattern is about" };
    const edit = (question, now, field) => async () => {
      const next = (await promptDialog(question, now, { confirmLabel: "Save" })).trim();
      if (!next || next === now) return;
      await call(at, "PATCH", { [field]: next })
        .then(() => pushRequestUndo(undoWords[field], at, "PATCH", { [field]: now }, { [field]: next }, changed))
        .catch(fail);
    };
    let undoIds = [];
    const dismiss = () => call(`${at}/dismiss`, "POST").then((done) => (undoIds = done.correction_ids || []));
    const items = [{ label: "ph:pencil-simple Edit", title: "Say it in your own words", run: edit("What should it say?", said, "sentence") }];
    if (subject) items.push({ label: "ph:tag Change what it is about", title: "Name what it is about; the tag it was found under still reaches it", run: edit("What is it about?", subject, "subject") });
    //: Not right is worded once, beside Confirm (`INSIGHT_VERDICT_ITEMS`, status.js).
    items.push(
      {
        label: INSIGHT_VERDICT_ITEMS.find((item) => item.verdict === "dismiss").label,
        title: "Not right: forget it and never show this pattern again",
        run: () =>
          dismiss()
            .then(() =>
              offerUndo("Marked a pattern not right", "Not right: this pattern won't be shown again.", async () => {
                for (const id of undoIds) await apiJson(`/learned/corrections/${id}`, { method: "DELETE" });
                await call(`${at}/restore`, "POST");
              }, dismiss)
            )
            .catch(fail),
      },
      {
        label: "ph:trash Remove",
        title: "Forget you confirmed it; the pattern may be shown again",
        danger: true,
        run: () =>
          call(at, "DELETE")
            .then(() => offerUndo("Removed a confirmed pattern", "Removed.", () => call(`${at}/restore`, "POST"), () => call(at, "DELETE")))
            .catch(fail),
      }
    );
    return items;
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { confirmedPatternItems });
})();
