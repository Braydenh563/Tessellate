// skills.js: skills, the composer's nudges, agent tools, sharing, saving a
// file, batch operations. Moved out of app.js on 2026-09-26 as one contiguous
// range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md). A classic
// script sharing app.js's globals, loaded in app.js's old order; nothing in an
// earlier file calls into it while the page loads (scratchpad/appjs-map.js
// --check).

// --- skills (§21): named, repeatable jobs over the notebook ----------------------

// A skill used to be {name, prompt} and clicking one dropped its prompt into
// the chat box. It is now a job: what to do, the steps to do it in, the tools
// it may use, and the values it asks for first. The built-in ones used to be
// a list right here, which meant the server could not resolve a skill the
// user clicked; they are served from GET /skills now, alongside the user's own.
let skillsCache = [];
//: The user skills folder (B8): its path and the files there that did not load.
const skillsState = { folder: null, limits: { steps: 10, tools: 12, inputs: 5 }, dismissChat: null };

async function loadSkills() {
  const body = await apiJson("/skills").catch(() => null);
  if (!body) return skillsCache;
  skillsCache = body.skills || [];
  if (body.limits) skillsState.limits = body.limits;
  skillsState.folder = body.folder || null;
  return skillsCache;
}

function allSkills() {
  return skillsCache;
}

//: The skills saved in Settings, which are what `saveSkillList` writes back.
//: Not the folder's: those are the person's own files, and copying one into
//: the preferences would leave a second copy behind when the file is deleted.
function customSkills() {
  return skillsCache.filter((skill) => !skill.builtin && !skill.folder);
}

// Which custom skill (by name) the editor is currently editing, if any.
// Tracking it lets Edit rename a skill instead of leaving a duplicate.
let editingSkillName = null;

// Steps and inputs are edited as one-per-line text, which is the shape people
// already write a list in. An input is "name" or "name: the question to ask".
function stepsToText(steps) {
  return (steps || []).join("\n");
}

function inputsToText(inputs) {
  return (inputs || [])
    .map((item) => (item.label && item.label !== `${item.name}?` ? `${item.name}: ${item.label}` : item.name))
    .join("\n");
}

function startEditingSkill(skill) {
  editingSkillName = skill.name;
  // The form is folded until wanted (index.html, `#skill-add-fold`).
  const fold = $("skill-add-fold");
  if (fold) fold.open = true;
  $("skill-name").value = skill.name;
  $("skill-prompt").value = skill.prompt;
  $("skill-description").value = skill.description || "";
  $("skill-steps").value = stepsToText(skill.steps);
  $("skill-inputs").value = inputsToText(skill.inputs);
  renderSkillToolPicker(skill.tools || []);
  renderSkillVerifyPicker(skill.verify || null);
  $("skill-add").textContent = "Save changes";
  $("skill-cancel").classList.remove("hidden");
  $("skill-status").textContent = `Editing “${skill.name}”…`;
  $("skill-prompt").focus();
}

function stopEditingSkill() {
  editingSkillName = null;
  for (const id of ["skill-name", "skill-prompt", "skill-description", "skill-steps", "skill-inputs"]) {
    $(id).value = "";
  }
  renderSkillToolPicker([]);
  setSkillVerify(null);
  $("skill-add").textContent = "Add skill";
  $("skill-cancel").classList.add("hidden");
  $("skill-status").textContent = "";
}

// The tools a skill may use, as checkboxes over the real registry, so a
// skill cannot name a tool that doesn't exist, and picking them is a matter
// of reading rather than remembering.
async function renderSkillToolPicker(selected = []) {
  const box = $("skill-tool-list");
  if (!box) return;
  const chosen = new Set(selected);
  const catalog = await apiJson("/chat/tools").catch(() => null);
  box.replaceChildren();
  if (!catalog) {
    box.textContent = "Could not load the tools a skill can use. Close this and open it again.";
    return;
  }
  for (const tool of catalog) {
    const label = document.createElement("label");
    label.className = "check-row";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = tool.name;
    input.checked = chosen.has(tool.name);
    const text = document.createElement("span");
    text.textContent = tool.name;
    text.title = tool.description;
    label.append(input, text);
    box.appendChild(label);
  }
}

//: **The skill's postcondition, in the editor** (CHAT_PLAN decision 10b).
//: `skills.normalise` has read and written a `verify` block since the harness
//: landed and nothing offered one, so only the shipped skills could say what
//: "it worked" means for them. The tool list comes from the server's own
//: catalog (`counts: true`) rather than a list written here, for the same
//: reason the tool picker does: a name typed into the frontend is a name that
//: drifts.
async function renderSkillVerifyPicker(block) {
  const select = $("skill-verify-tool");
  if (!select) return;
  const catalog = await apiJson("/chat/tools").catch(() => []);
  const counting = catalog.filter((tool) => tool.counts);
  select.replaceChildren();
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "nothing (no check)";
  select.appendChild(none);
  for (const tool of counting) {
    const option = document.createElement("option");
    option.value = tool.name;
    option.textContent = tool.name;
    option.title = tool.description;
    select.appendChild(option);
  }
  setSkillVerify(block);
}

function setSkillVerify(block) {
  const spec = block || {};
  const expect = spec.expect || {};
  const [predicate, value] = Object.entries(expect)[0] || ["unchanged", true];
  $("skill-verify-tool").value = spec.tool || "";
  $("skill-verify-expect").value = predicate;
  $("skill-verify-value").value = predicate === "unchanged" ? 0 : Number(value) || 0;
  $("skill-verify-untagged").checked = Boolean((spec.args || {}).untagged);
  syncSkillVerifyRow();
}

//: The number is meaningless beside "unchanged", and a disabled control that
//: still shows a value reads as a setting that is being ignored, so it is
//: hidden rather than greyed. The same reasoning as the run dialog's own
//: optional rows.
function syncSkillVerifyRow() {
  const predicate = $("skill-verify-expect").value;
  $("skill-verify-value").classList.toggle("hidden", predicate === "unchanged");
}

// Run a skill. The server owns what a skill is, so this sends its name and
// the values it asked for, not a prompt assembled here. The mode a skill runs
// in is settled in `startSkill`, which both entry points go through.
function runSkill(skill) {
  if ((skill.inputs || []).length) {
    askSkillInputs(skill, (values) => startSkill(skill, values));
    return;
  }
  startSkill(skill, {});
}

// A plan the model drew for the last request, run the way a skill is run
// (§35K). The steps are sent back rather than parked on the server, for the
// same reason `ask_user`'s answer is: nothing to expire, nothing lost on a
// reload, and the run is a message in the conversation like any other.
function startPlannedRun(goal, steps) {
  switchTab("chat"); // same reason as startSkill: the run happens in the chat
  sendChatMessage(goal, { plan: { goal, steps }, skipPlanMode: true });
}

async function startSkill(skill, values) {
  // Both entry points land here, the Skill dropdown and a run the agent started
  // itself (§33): so the dashboard's recent-skill buttons cover both.
  noteSkillRun(skill.name);
  // **And so does the dashboard's Skill chip, which is why this is here.**
  // Reported: *"when I click on the suggested skills in the dashboard, it runs
  // the skill but doesn't navigate me to it."* Exactly right: the run started,
  // the answer streamed into a tab nobody was looking at, and the dashboard sat
  // there as though the button had done nothing. A skill *is* a message in the
  // conversation, so starting one has to take you to the conversation. From
  // the Skill dropdown, where you are already here, this is a no-op.
  switchTab("chat");
  //: **A skill runs in Agent mode, and says so** (INBOX 39, the owner's
  //: decision).
  //:
  //: The rule until now was the opposite: an *action* skill carried its own
  //: permission, so the backend turned tools on for that one call
  //: (`skill["acts"]` in routes_chat.py) and the toggle was deliberately left
  //: alone. As a contract that is tidy; read as a person it is not. The
  //: segment said "Ask" while the run was creating and tagging notes, a
  //: non-acting skill quietly got a different toolbox depending on a control
  //: nobody had touched, and the mode a run actually used was invisible until
  //: the meta line under the answer.
  //:
  //: So the mode moves, once, before the run starts, and stays moved: a
  //: setting that flips back on its own is a worse surprise than one that
  //: does not. Announced in a line, the way Plan mode already announces the
  //: same switch, because a mode that changed under you and said so beats
  //: "why can it suddenly do that?".
  //:
  //: Awaited, not fired off: `sendChatMessage` reads `#tools-toggle` to decide
  //: what this turn sends and what the saved turn records, so the checkbox has
  //: to be true before the message leaves.
  if (!$("tools-toggle").checked) {
    await setChatMode("agent");
    toast("Switched to Agent for this skill.");
  }
  const given = Object.values(values).filter(Boolean).join(", ");
  sendChatMessage(`${skill.name}${given ? `, ${given}` : ""}`, {
    skill: skill.name,
    skillInputs: values,
    // A skill is its own instruction. Wrapping it in "plan this first" would
    // plan a thing that already has steps.
    skipPlanMode: true,
  });
}

// One dialog for everything a skill asks for. Two window.prompt boxes in a
// row is how this started, and the second one gave no clue which skill it
// belonged to or what the first answer had been.
function askSkillInputs(skill, done) {
  const overlay = $("skill-run-overlay");
  const fields = $("skill-run-fields");
  $("skill-run-title").textContent = skill.name;
  $("skill-run-description").textContent = skill.description || skill.prompt;
  fields.replaceChildren();
  const inputs = [];
  for (const item of skill.inputs || []) {
    const label = document.createElement("label");
    label.className = "field";
    const text = document.createElement("span");
    text.textContent = item.label || item.name;
    const box = document.createElement("input");
    box.type = "text";
    box.value = item.default || "";
    box.maxLength = 200;
    box.placeholder = item.required ? "" : "optional";
    label.append(text, box);
    fields.appendChild(label);
    inputs.push({ item, box });
  }

  const close = () => {
    overlay.classList.add("hidden");
    document.removeEventListener("keydown", onKey);
  };
  const submit = () => {
    const values = {};
    for (const { item, box } of inputs) {
      const value = box.value.trim();
      if (!value && item.required && !item.default) {
        box.focus();
        // Nothing is sent half-filled: a skill run with a blank {{topic}}
        // searches the whole notebook for nothing and reads as being ignored.
        toast(`“${skill.name}” needs ${item.label || item.name}.`, "info");
        return;
      }
      values[item.name] = value;
    }
    close();
    done(values);
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
    else if (event.key === "Enter" && event.target.tagName === "INPUT") submit();
  };

  $("skill-run-go").onclick = submit;
  $("skill-run-cancel").onclick = close;
  document.addEventListener("keydown", onKey);
  overlay.classList.remove("hidden");
  inputs[0]?.box.focus();
}

// Skills as a dropdown rather than a row of chips. Ten built-ins plus up to
// thirty of your own is a wrapping wall of buttons that pushes the message box
// off the screen, and every one of them is a click you can make by accident
// while reaching for the text area. A select is one line, groups "yours" apart
// from the built-ins, and, the part that matters, leaves room to say what a
// skill DOES next to its name instead of hiding it in a hover.
// The skills group in the chat dock: everything about running a saved job,
// in one place.
//
// It was a lightning mark, a select, a Run button and a bare "＋" that opened
// Settings: with the "run skills step-by-step" preference stranded three
// controls away inside the gear popup, where nobody found it. Asked for
// directly: fold the "+" into the combobox as an option, put the step-by-step
// choice next to the skill it applies to as a two-option pill, and keep Run.
//
// The pill and the hidden checkbox is the same pattern the Ask/Agent pair
// already uses in this strip: the checkbox stays as the thing the rest of the
// app reads and stores (`sendChatMessage` reads `#skill-manual-toggle`), and
// the pill is what a person operates. Two named options rather than a tickbox,
// because a tickbox states one mode and leaves the other implied, "not
// step-by-step" had no name and no description.
const SKILL_MANAGE_VALUE = "__manage__";

//: The dropdown's two dismissal listeners on `document`, dropped with the
//: build they belong to: `loadChatSkills` runs at boot and again after every
//: skill saved in Settings, and each run left its pair behind, holding the
//: dropdown it was built for (listenerrounds.js: +35 listeners a rebuild).

async function loadChatSkills() {
  await loadSkills();
  const box = $("chat-skills");
  box.replaceChildren();

  const label = document.createElement("span");
  label.className = "muted chat-skill-mark";
  setLabel(label, "ph:lightning");
  label.title = "Skills: saved jobs you can run over your notes";

  const select = document.createElement("select");
  select.className = "small-select chat-skill-select";
  select.id = "chat-skill-select";
  select.setAttribute("aria-label", "Activate a skill");
  fillSkillSelect(select);

  // Chosen, then run: rather than running on change. A dropdown that fires an
  // action the instant it changes cannot be browsed, and these actions edit
  // the notebook. "Add or edit skills…" is the exception: it opens a settings
  // pane, which is safe and is the whole reason to pick it.
  const run = smallButton("ph:play Run", "Run the selected skill", () => {
    const chosen = allSkills().find((s) => s.name === select.value);
    if (chosen) runSkill(chosen);
  });
  run.disabled = true;
  select.addEventListener("change", () => {
    if (select.value === SKILL_MANAGE_VALUE) {
      select.value = "";
      run.disabled = true;
      openSettingsModal("skills");
      return;
    }
    run.disabled = !select.value;
    // What the skill does lives in the select's own tooltip rather than a line
    // of prose beside it, it was the widest thing in the dock and clipped at
    // 120 characters anyway.
    const chosen = allSkills().find((s) => s.name === select.value);
    select.title = chosen ? skillSummary(chosen) : "Run one of your saved skills";
  });

  // **One "Skills" dropdown, not four controls loose in the strip.** Asked for
  // directly, twice: the selector, the Auto|Manual pill and Run belong inside
  // a Skills menu, not spread across the dock competing with Ask/Agent/Web/
  // Plan for width. Running a skill is one job; it should occupy one control
  // until you are actually doing it.
  //
  // Built on the same trigger-plus-panel shape as the gear popup two groups
  // along (.chat-dock-more), because a second popup pattern in one strip is
  // how a toolbar starts looking assembled rather than designed.
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.id = "chat-skills-btn";
  trigger.className = "ghost small";
  trigger.setAttribute("aria-haspopup", "dialog");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-controls", "chat-skills-panel");
  trigger.title = "Skills: saved jobs you can run over your notes";
  setLabel(trigger, "ph:lightning Skills");
  //: B8: a skill file dropped into the skills folder is in the list the next
  //: time the menu opens, without a restart, so opening it asks again.
  trigger.addEventListener("click", () => {
    // Runs before the toggle below, so "true" here means it is closing.
    if (trigger.getAttribute("aria-expanded") === "true") return;
    loadSkills().then(() => fillSkillSelect(select));
  });
  buildSkillsPanel(box, label, select, run, trigger);
}

//: The select's options from `allSkills()`, keeping what was chosen when it is
//: still there; run again each time the Skills menu opens (B8).
function fillSkillSelect(select) {
  const chosen = select.value;
  select.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Activate a skill…";
  select.appendChild(placeholder);

  //: "Edits notes" is a group, not a suffix: a suffix wrapped long names onto two lines.
  const groups = {};
  for (const skill of allSkills()) (groups[`${skill.builtin ? "Built-in" : "Yours"}, ${skill.changes ? "edits notes" : "read only"}`] ||= []).push(skill);
  for (const [key, list] of Object.entries(groups).sort()) {
    const group = document.createElement("optgroup");
    group.label = key;
    for (const skill of list) {
      const option = document.createElement("option");
      option.value = option.textContent = skill.name;
      option.title = skillSummary(skill);
      //: Phase E, decision 2: measured below the bar on a small model, so
      //: shown with why rather than offered and hoped.
      //: O7 (B69): with no model, a skill the composer cannot read off the
      //: notes says so and waits; the ones it runs stay open.
      if (aiIsOff() && !skill.composer) {
        option.textContent += "  (needs a model)";
        option.title = "Needs a model: this skill writes in its own words. Connect one in Settings, Models.";
        option.disabled = true;
      } else if (skill.needs_larger_model) {
        option.textContent += "  (needs a larger model)";
        option.title = skill.needs_larger_model;
        option.disabled = true;
      }
      group.appendChild(option);
    }
    select.appendChild(group);
  }

  // Managing skills is one of the things you come to this control to do, so it
  // is in the list rather than beside it as an unlabelled "＋". Its own group,
  // at the bottom, so it never sits among the runnable options.
  const manageGroup = document.createElement("optgroup");
  manageGroup.label = "Manage";
  const manage = document.createElement("option");
  manage.value = SKILL_MANAGE_VALUE;
  manage.textContent = "Add or edit skills…";
  manageGroup.appendChild(manage);
  select.appendChild(manageGroup);

  if ([...select.options].some((option) => option.value === chosen)) select.value = chosen;
}

//: The Skills menu around the select: built once per `loadChatSkills`.
function buildSkillsPanel(box, label, select, run, trigger) {
  const panel = document.createElement("div");
  panel.id = "chat-skills-panel";
  panel.className = "chat-skills-panel hidden";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Run a skill");

  //: Every listener this build puts on something that outlives it (document,
  //: the Settings checkbox the pace pill mirrors) goes with the build.
  skillsState.dismissChat?.abort();
  skillsState.dismissChat = new AbortController();
  const { signal } = skillsState.dismissChat;

  const pickRow = document.createElement("label");
  pickRow.className = "chat-skills-row";
  const pickLabel = document.createElement("span");
  pickLabel.className = "muted";
  pickLabel.textContent = "Skill";
  pickRow.append(pickLabel, select);

  const paceRow = document.createElement("div");
  paceRow.className = "chat-skills-row";
  const paceLabel = document.createElement("span");
  paceLabel.className = "muted";
  paceLabel.textContent = "Pace";
  paceRow.append(paceLabel, skillPacePill(signal));

  const runRow = document.createElement("div");
  runRow.className = "chat-skills-run";
  runRow.appendChild(run);

  panel.append(pickRow, paceRow, runRow);

  //: `refocus`: Escape or Run, with the focus inside, hands it back to the
  //: trigger; hidden with the focus in it, it fell to the page (WCAG 2.4.3).
  const close = (refocus) => {
    const had = refocus === true && panel.contains(document.activeElement);
    panel.classList.add("hidden");
    trigger.setAttribute("aria-expanded", "false");
    if (had) trigger.focus();
  };
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = trigger.getAttribute("aria-expanded") === "true";
    trigger.setAttribute("aria-expanded", String(!open));
    panel.classList.toggle("hidden", open);
    //: See `focusSelect`: a bare `select.focus()` here left the skills panel
    //: open with nothing focused, so the first Tab went to the top of the page.
    if (!open) focusSelect(select);
  });
  document.addEventListener("click", (event) => {
    if (!box.contains(event.target)) close();
  }, { signal });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close(true);
  }, { signal });
  // Running one is the end of the interaction, so the menu gets out of the way.
  run.addEventListener("click", () => close(true));

  // The trigger says which skill is armed, so the dock still answers "what is
  // this about to do?" without being opened.
  select.addEventListener("change", () => {
    setLabel(
      trigger,
      select.value && select.value !== SKILL_MANAGE_VALUE
        ? `ph:lightning ${select.selectedOptions[0].textContent}`
        : "ph:lightning Skills"
    );
  });

  box.append(trigger, panel);
  box.classList.remove("hidden");
  void label; // the group's mark is the trigger's own icon now
}

// Auto | Manual, over the hidden #skill-manual-toggle checkbox that the rest of
// the app reads. Kept in sync both ways: Settings can still flip the checkbox,
// and the pill follows.
//: `signal`: the pill mirrors `#skill-manual-toggle`, a checkbox in Settings
//: that outlives every pill built on it, and the `change` listener it puts
//: there held each old pill, and through it the whole dropdown (listenerrounds.js).
function skillPacePill(signal) {
  const seg = document.createElement("div");
  seg.className = "seg seg-compact chat-skill-pace";
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "How a skill runs");

  const toggle = $("skill-manual-toggle");
  const options = [
    ["auto", "Auto", "Run every step straight through without stopping."],
    ["manual", "Manual", "Pause after each step so you can add something before it continues."],
  ];
  const buttons = [];
  for (const [value, text, title] of options) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.pace = value;
    button.textContent = text;
    button.title = title;
    button.addEventListener("click", () => {
      if (toggle) {
        toggle.checked = value === "manual";
        // `change`, so anything else listening to the stored preference, the
        // Settings row, a future autosave, hears it. Setting .checked in JS
        // does not fire one on its own, which is the classic way a pill and
        // the thing it controls drift apart.
        toggle.dispatchEvent(new Event("change", { bubbles: true }));
      }
      paint();
    });
    buttons.push(button);
    seg.appendChild(button);
  }

  function paint() {
    const manual = Boolean(toggle?.checked);
    for (const button of buttons) {
      const on = (button.dataset.pace === "manual") === manual;
      button.classList.toggle("active", on);
      button.setAttribute("aria-pressed", String(on));
    }
  }
  toggle?.addEventListener("change", paint, { signal });
  paint();
  return seg;
}

// --- the composer's two nudges (BACKLOG: agent-mode + skill auto-detect) -----
//
// Both capabilities were reachable only by people who already knew where the
// controls were. Typing "delete the notes I tagged scratch" in Ask mode gets a
// careful description of how one might do that, because Ask genuinely cannot
// act; and a skill someone wrote last month for exactly that job sits behind a
// dropdown behind a popup. Neither is a bug, they are both "a capability with
// no control is a capability most people never meet", the same observation
// that put the Plan button in the dock.
//
// The rules this follows, because a nudge that gets any of them wrong is worse
// than no nudge at all:
//
// - **It never acts.** It offers a button. Switching modes and running a skill
//   are both things that change what happens to your notes.
// - **Dismiss means dismissed.** Per draft, per kind, clearing the box or
//   sending resets it, so it does not become a thing you dismiss every time.
// - **It stays quiet when it has nothing to add**: already in Agent mode, or
//   the text is too short to be a request at all.
//
// Matching is a heuristic here rather than a model call for the same reason
// ai/intent.py's is: it runs on every keystroke (debounced), so it has to be
// instant, and a local model call per keystroke is neither.

// Verbs that only mean something if the assistant can act. Deliberately
// narrow: "write" and "find" are absent because "write me a poem" and "find
// out what X means" are ordinary Ask questions, and a nudge that fires on
// those is noise on most messages.
const AGENT_INTENT_RE = new RegExp(
  "\\b(?:" +
    "delete|remove|archive|rename|merge|de-?duplicate|dedupe|" +
    "tag|untag|re-?tag|link|unlink|organi[sz]e|tidy|clean ?up|sort|categori[sz]e|" +
    "create|make|add|save|append|update|edit|change|move|" +
    "schedule|remind me|set a reminder|" +
    //: "Draft", "outline" and "generate" ask for something written; "fix",
    //: "plan", "format" and "translate" are left out because "how do I
    //: format a date" is a question, not a request to act.
    "draft|outline|generate|" +
    "summari[sz]e (?:my|all|the|every)|go through (?:my|all|the)" +
    ")\\b",
  "i"
);

// A second, independent trigger: things that need the web tool specifically.
const AGENT_WEB_RE = /\b(?:search the web|look (?:this |it )?up online|google|browse to|open (?:this |the )?(?:page|link|url)|https?:\/\/)/i;

// A draft is "a request" only if it also names something in the notebook, or
// is plainly imperative. Without this, "I should probably tag things better"
//, a musing, not an instruction, fires the nudge.
const AGENT_OBJECT_RE = /\b(?:not(?:e|es)|entr(?:y|ies)|tag(?:s|ged)?|document|documents|space|spaces|reminder|reminders|task|tasks|link(?:s|ed)?|my notebook|everything)\b/i;

// Which nudges this draft has been told to stop offering. Reset when the box
// empties or a message is sent, see the input handler at the bottom of this
// file.
const chatNudgeDismissed = new Set();

function looksLikeAnAgentRequest(text) {
  if (text.trim().length < 8) return false;
  if (AGENT_WEB_RE.test(text)) return true;
  return AGENT_INTENT_RE.test(text) && AGENT_OBJECT_RE.test(text);
}

// The skill whose name (or description) the draft is most plainly asking for,
// or null. Scored rather than first-match: with a dozen skills installed, the
// one that shares three words with what you typed is a better guess than
// whichever happens to sort first.
function skillMatchingDraft(text) {
  const haystack = text.toLowerCase();
  if (haystack.trim().length < 8) return null;
  let best = null;
  let bestScore = 0;
  for (const skill of allSkills()) {
    const name = String(skill.name || "");
    if (!name) continue;
    // A name typed out in full is as explicit as it gets, nothing scored
    // word-by-word should be able to beat it.
    let score = haystack.includes(name.toLowerCase()) ? 10 : 0;
    // Words short enough to be incidental ("a", "the", "my", "and") match
    // everything and would make every skill look relevant.
    const words = `${name} ${skill.description || ""}`
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length > 4);
    const seen = new Set();
    for (const word of words) {
      if (seen.has(word)) continue;
      seen.add(word);
      if (haystack.includes(word)) score += 1;
    }
    if (score > bestScore) {
      bestScore = score;
      best = skill;
    }
  }
  // Two independent words, or the name in full. One shared word is a
  // coincidence on any notebook with more than a few skills.
  return bestScore >= 2 ? best : null;
}

function renderChatNudge() {
  const box = $("chat-nudge");
  if (!box) return;
  const text = $("chat-input")?.value || "";
  box.replaceChildren();

  const offers = [];
  // Mode first: it changes what the message can do at all, so it outranks
  // "there is a saved job for this".
  if (
    !chatNudgeDismissed.has("agent") &&
    !$("tools-toggle")?.checked &&
    looksLikeAnAgentRequest(text)
  ) {
    offers.push({
      kind: "agent",
      icon: "ph:strategy",
      text: "That reads like something to do, not something to answer. Ask mode can't touch your notes.",
      action: "Switch to Agent",
      run: () => setChatMode("agent"),
    });
  }
  //: A skill runs on a model with tools, so the offer waits for both (the
  //: owner: "The ai model isnt running, skills are disabled, and it still
  //: suggests skills").
  if (!chatNudgeDismissed.has("skill") && $("tools-toggle")?.checked && !aiIsOff()) {
    const skill = skillMatchingDraft(text);
    if (skill) {
      offers.push({
        kind: "skill",
        icon: "ph:lightning",
        text: `You have a skill for this: “${skill.name}”.`,
        action: "Run it",
        title: skillSummary(skill),
        run: () => runSkill(skill),
      });
    }
  }

  // One at a time. Two stacked nudges above a one-line composer is the dock
  // arguing with you rather than helping.
  const offer = offers[0];
  box.classList.toggle("hidden", !offer);
  if (!offer) return;

  const mark = document.createElement("span");
  mark.className = "chat-nudge-mark";
  setLabel(mark, offer.icon);
  const line = document.createElement("span");
  line.className = "chat-nudge-text";
  line.textContent = offer.text;
  const act = smallButton(offer.action, offer.title || offer.action, () => {
    // Whatever the offer was, taking it ends it, re-offering the switch you
    // just made would be the dock talking to itself.
    chatNudgeDismissed.add(offer.kind);
    renderChatNudge();
    offer.run();
  }, false);
  const dismiss = smallButton("ph:x", "Dismiss this suggestion", () => {
    chatNudgeDismissed.add(offer.kind);
    renderChatNudge();
  });
  dismiss.classList.add("chat-nudge-dismiss");
  box.append(mark, line, act, dismiss);
}

// Cleared when the draft is, a new message is a new question, and the
// suggestion you turned down for the last one should not follow it.
function resetChatNudge() {
  chatNudgeDismissed.clear();
  renderChatNudge();
}

function skillSummary(skill) {
  const lines = [skill.description || skill.prompt];
  if (skill.changes) lines.push("(This one changes your notes, deletes still ask first.)");
  if ((skill.steps || []).length) {
    lines.push("", ...skill.steps.map((step, i) => `${i + 1}. ${step}`));
  }
  if ((skill.tools || []).length) lines.push("", `Tools: ${skill.tools.join(", ")}`);
  if ((skill.inputs || []).length) {
    lines.push("", `Asks you for: ${skill.inputs.map((i) => i.name).join(", ")}`);
  }
  return lines.join("\n");
}

async function saveSkillList(skills) {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ skills }),
  });
  await loadSkills();
  renderSkillSettings();
  loadChatSkills();
}

function skillRow(skill) {
  const li = document.createElement("li");
  const row = document.createElement("div");
  row.className = "entry-meta skill-row";
  //: A title, a label and facts, not six pills of one weight (owner: "there
  //: is still missing distinguishing between titles that used to be
  //: badges"). The recipe is `.item-title`, `.item-label` and `.item-fact`
  //: in 08-consistency.css, shared with the personas.
  row.appendChild(chip(skill.name, "item-title"));
  if (skill.builtin) row.appendChild(chip("Built-in", "item-label"));
  if (skill.folder) {
    const from = chip("From the skills folder", "item-label");
    from.title = `The file ${skill.file}; edit or delete it there`;
    row.appendChild(from);
  }
  if (skill.changes) row.appendChild(chip("ph:pencil-simple Changes notes", "item-fact item-writes"));
  if (skill.needs_larger_model) {
    const larger = chip("Needs a larger model", "item-fact");
    larger.title = skill.needs_larger_model;
    row.appendChild(larger);
  }
  if ((skill.steps || []).length) {
    row.appendChild(chip(nounCount(skill.steps.length, "step"), "item-fact"));
  }
  if ((skill.tools || []).length) {
    row.appendChild(chip(`${skill.tools.length} tools`, "item-fact"));
  }
  for (const item of skill.inputs || []) row.appendChild(chip(`Asks for ${item.name}`, "item-fact"));
  // Its own class, not `persona-preview`. That one is `white-space: nowrap`
  // with an ellipsis, which is right for a persona (one line of voice) and
  // wrong here: a skill's description is the only thing that says what it
  // *does*, and clipping it to the width left over after five chips showed
  // three words. Reported twice. It wraps onto its own line now.
  const note = document.createElement("span");
  note.className = "muted skill-blurb";
  note.textContent = skill.description || skill.prompt;
  row.appendChild(note);
  if (!skill.builtin && !skill.folder) {
    const actions = document.createElement("span");
    actions.className = "entry-actions";
    actions.appendChild(
      smallButton("Edit", "Edit this skill", () => startEditingSkill(skill))
    );
    actions.appendChild(
      smallButton("Delete", "Remove this skill", async () => {
        if (!(await confirmDialog(`Delete the “${skill.name}” skill?`))) return;
        await saveSkillList(customSkills().filter((s) => s.name !== skill.name));
      })
    );
    li.append(row, actions);
  } else {
    li.appendChild(row);
  }
  return li;
}

async function renderSkillSettings() {
  const list = $("skill-list");
  showSkeletons(list, 3, "li");
  try {
    await loadSkills();
  } finally {
    clearSkeletons(list);
  }
  list.replaceChildren();
  for (const skill of allSkills()) list.appendChild(skillRow(skill));
  renderSkillFolderLine();
  if (!$("skill-tool-list").children.length) renderSkillToolPicker([]);
  if (!$("skill-verify-tool").children.length) renderSkillVerifyPicker(null);
}

//: Where the skills folder is and which of its files did not load (B8): a file
//: that is not in the list says why here rather than being silently absent.
function renderSkillFolderLine() {
  const line = $("skill-folder-line");
  if (!line) return;
  const folder = skillsState.folder || {};
  line.textContent = folder.path
    ? `Skills folder: ${folder.path}. A Markdown file saved there is listed here without a restart.`
    : "";
  for (const problem of folder.problems || []) {
    const item = document.createElement("span");
    item.className = "skill-folder-problem";
    item.textContent = problem.file ? `${problem.file}: ${problem.message}.` : `${problem.message}.`;
    line.append(document.createElement("br"), item);
  }
}

// --- Wave O: agent-tools toggles ----------------------------------------------------

// How many tool descriptions each message carries (§11a). Saved on change
// rather than behind an Apply button, the search-engine picker taught us
// that a control which saves nothing until later reads as broken, because
// the next status poll paints the old value back over it.
function renderToolFocus(current) {
  for (const radio of document.querySelectorAll('input[name="tool-focus"]')) {
    radio.checked = radio.value === current;
    radio.onchange = async () => {
      if (!radio.checked) return;
      const status = $("tool-focus-status");
      status.textContent = "Saving…";
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ tool_focus: radio.value }),
      });
      status.textContent =
        radio.value === "auto"
          ? "Each message is offered the tools it needs."
          : "Every message is offered every tool.";
    };
  }
}

//: **The Phase B setting, given the control it never had.** `small_model_mode`
//: has been on GET/PUT /preferences since the skills reform's backend half,
//: read by the chat route on every run, with nothing anywhere in the app that
//: could change it, so every notebook ran on `auto` whatever its owner wanted.
//: Saved on change for the same reason the tool-focus radios above are: a
//: control that waits for an Apply button reads as broken here, because the
//: next preferences render paints the old value back over it.
function renderSmallModelMode(current) {
  const select = $("small-model-mode");
  if (!select) return;
  select.value = current || "auto";
  renderSmallModelAuto();
}

//: **The run budget** (Brief 13), the same shape as the two controls above:
//: saved on change, because a control that waits for an Apply button reads as
//: broken here, the next preferences render paints the old value back over it.
//: Both fields together in one request, so a person who edits one and then the
//: other does not race two writes of the same preferences file.
function renderRunBudget(prefs) {
  const tokens = $("run-budget-tokens");
  const seconds = $("run-budget-seconds");
  if (tokens) tokens.value = String(prefs.run_budget_tokens ?? 20000);
  if (seconds) seconds.value = String(prefs.run_budget_seconds ?? 90);
}

//: One tool's switch, saved. A refused save puts the switch back and says why:
//: the handler used to `await` with nothing to catch it, so a 422 was an
//: unhandled rejection and the switch stayed where the server disagreed (found
//: by the deepflows sweep, which turned all the tools off).
async function saveToolSwitch(check, name) {
  const next = new Set(prefsCache.disabled_tools || []);
  if (check.checked) next.delete(name);
  else next.add(name);
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ disabled_tools: [...next] }),
    });
  } catch (error) {
    check.checked = !check.checked;
    toast(error.message || "Couldn't save that. Try again.", true);
    return;
  }
  // The "N of 51 on" count is only true until someone flips one.
  applyToolFilter();
}

async function renderToolSettings() {
  renderMcpSnippet();
  const list = $("tool-list");
  showSkeletons(list, 4, "li");
  const [catalog, prefs] = await Promise.all([
    apiJson("/chat/tools").catch(() => []),
    apiJson("/preferences").catch(() => ({ disabled_tools: [] })),
  ]);
  clearSkeletons(list);
  prefsCache = prefs;
  renderToolFocus(prefs.tool_focus || "auto");
  renderSmallModelMode(prefs.small_model_mode || "auto");
  renderRunBudget(prefs);
  const disabled = new Set(prefs.disabled_tools || []);
  list.replaceChildren();
  //: Grouped by what a tool does to the notebook (CHAT_PLAN, INBOX 71: "a
  //: grouped table (read, write, destructive)"), each group under an
  //: `h4.setting-subhead` (DESIGN.md: a subdivision inside a group) that
  //: spans both columns. Within a group, the catalog's own order.
  for (const [key, title] of TOOL_GROUPS) {
    const members = catalog.filter((t) => (t.group || "read") === key);
    if (!members.length) continue;
    const head = document.createElement("li");
    head.className = "tool-group-head";
    head.dataset.group = key;
    const h4 = document.createElement("h4");
    h4.className = "setting-subhead";
    h4.textContent = title;
    head.append(h4);
    list.append(head);
    for (const tool of members) appendToolRow(list, tool, disabled, key);
  }
  applyToolFilter();
}

//: The four groups, in the order a person scanning for risk reads them.
const TOOL_GROUPS = [
  ["read", "Reads your notebook"],
  ["write", "Changes your notebook"],
  ["confirm", "Asks you first"],
  ["online", "Reaches the web"],
];

function appendToolRow(list, tool, disabled, group) {
  const li = document.createElement("li");
  li.dataset.group = group;
  //: What a Tools and features row for this tool lands on (`ai-tool` in
  //: REVEAL_TARGETS).
  li.dataset.tool = tool.name;
  const label = document.createElement("label");
  label.className = "tool-row setting-check";
  const check = document.createElement("input");
  check.type = "checkbox";
  check.checked = !disabled.has(tool.name);
  // web_search is gated by the separate online opt-in, show why it's off.
  if (tool.online && !tool.enabled && !disabled.has(tool.name)) {
    check.checked = false;
    check.disabled = true;
    check.title = "Enable web search in Preferences first";
  }
  check.addEventListener("change", () => saveToolSwitch(check, tool.name));
  const text = document.createElement("span");
  const name = document.createElement("strong");
  name.textContent = tool.name.replace(/_/g, " ");
  text.append(name);
  // The chips sit on their own line under the name, not after it on the
  // same one: the switch is centred on the name's line (the grid in
  // 03-dashboard-widgets.css), and a chip that wrapped would have made
  // that line two lines tall and pulled the switch off the name again.
  if (tool.destructive || tool.online) {
    const tags = document.createElement("span");
    tags.className = "tool-tags";
    if (tool.destructive) tags.append(chip("confirms first", "item-label is-warn"));
    if (tool.online) tags.append(chip("online", "item-label"));
    text.append(tags);
  }
  const desc = document.createElement("span");
  desc.className = "muted tool-desc";
  desc.textContent = tool.description;
  desc.title = tool.description || ""; // clamped to two lines; the whole of it on hover
  // The description goes *inside* the label's text column, not beside the
  // label in the <li>. That is what lets this row be `.setting-check`'s
  // grid, name and description stacked in column one, switch hard right , 
  // instead of a flex row whose switch tracked the length of each name.
  // It also makes the description part of the control's own hit area, the
  // way the hint under every other setting already is.
  text.append(desc);
  label.append(check, text);
  li.append(label);
  // Matched against by the filter below. Stored on the row rather than
  // re-read from the DOM on every keystroke, and lower-cased once here
  // instead of once per row per keystroke.
  li.dataset.search = `${tool.name} ${tool.description || ""}`.toLowerCase().replace(/_/g, " ");
  list.appendChild(li);
}

//: Narrow a fifty-one item list, and say how many are on.
//:
//: The first audit of Settings measured this section at **5,708px**, by some
//: way the longest scroll in the app, with every tool a name plus a
//: paragraph of description. Finding one meant scrolling past fifty others,
//: and nothing anywhere answered the question the list actually raises: how
//: many of these are switched on?
//:
//: Filtering hides rows rather than re-rendering them, so a checkbox keeps
//: its state and its listener while you type. Re-rendering would also lose
//: focus from the filter field on every keystroke.
function applyToolFilter() {
  const list = $("tool-list");
  const box = $("tool-filter");
  const count = $("tool-count");
  const empty = $("tool-filter-empty");
  if (!list) return;
  const needle = (box?.value || "").trim().toLowerCase();
  const rows = [...list.querySelectorAll(":scope > li[data-tool]")];
  let shown = 0;
  const groupsShown = new Set();
  for (const row of rows) {
    const hit = !needle || (row.dataset.search || "").includes(needle);
    row.classList.toggle("hidden", !hit);
    if (hit) {
      shown++;
      groupsShown.add(row.dataset.group);
    }
  }
  //: A group's head goes with its last matching row.
  for (const head of list.querySelectorAll(":scope > li.tool-group-head")) {
    head.classList.toggle("hidden", !groupsShown.has(head.dataset.group));
  }
  empty?.classList.toggle("hidden", shown > 0 || !rows.length);
  if (count) {
    // Two different questions, so two different answers: with no filter the
    // useful number is how many are enabled; while filtering it is how many
    // the search actually found.
    const on = rows.filter((r) => r.querySelector("input[type=checkbox]")?.checked).length;
    count.textContent = needle
      ? `${shown} of ${rows.length}`
      : `${on} of ${rows.length} on`;
  }
}

// --- Wave M: share skills/personas as JSON ------------------------------------------

function downloadJson(filename, payload) {
  return saveFile(
    filename,
    new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
  );
}

// --- saving a generated file (§35E) ----------------------------------------------
//
// Every export here used to build a Blob and click a hidden `<a download>`.
// That works in a browser tab and does nothing whatsoever in the desktop
// window: pywebview has no download handler, so the click is swallowed and
// the user gets no file and no error. Reported as "I don't think any of the
// file save features in the whole application work on the python desktop app",
// which was exactly right and true of all of them at once.
//
// So there are two paths, chosen by asking the server which shell it is
// serving rather than by sniffing the user agent, pywebview's user agent is
// not reliably distinguishable, and a wrong guess here is a silent failure in
// the direction we are trying to fix.
let isDesktopShell = null; // null = not yet asked
//: One `/health` read for both questions below.
let healthFactsOnce = null;

function healthFacts() {
  healthFactsOnce ||= apiJson("/health", { silent: true }).catch(() => null);
  return healthFactsOnce;
}

//: `/health` answers per device: a phone on the network is never the desktop
//: shell, so it downloads its exports to itself rather than writing them onto
//: the computer's disk (the owner, 2026-10-11: "I pressed open file location
//: for the support bundle on my phone and it opened up file explorer on my
//: computer").
async function desktopShell() {
  if (isDesktopShell === null) {
    const health = await healthFacts();
    isDesktopShell = !!(health && health.desktop);
  }
  return isDesktopShell;
}

//: The words the server refuses with (`api/this_computer.py` REFUSAL), shown
//: before the press rather than after it. tests/test_ui_recipes.py holds them equal.
const THIS_COMPUTER_ONLY = "Not available on this device. Do it on the computer Tessellate runs on.";

//: DESIGN.md, "A control that acts on the computer Tessellate runs on": on
//: another device, each `[data-this-computer]` block gets one note line and
//: dimmed controls, `="hide"` is hidden, and a press toasts the note instead
//: of asking the server for a 403. Help toggles inside still open.
async function markOtherDevice() {
  const health = await healthFacts();
  if (!health || health.this_computer !== false) return;
  document.documentElement.dataset.otherDevice = "1";
  for (const block of document.querySelectorAll("[data-this-computer]:not([data-this-computer='hide'])")) {
    const note = document.createElement("p");
    note.className = "muted small this-computer-note";
    note.textContent = THIS_COMPUTER_ONLY;
    if (block.tagName === "SECTION") block.prepend(note);
    else block.before(note);
  }
  document.addEventListener("click", refuseOnOtherDevice, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") refuseOnOtherDevice(event);
  }, true);
}

function onOtherDevice() {
  return document.documentElement.dataset.otherDevice === "1";
}

//: At load, not from `startApp`: `/health` is open before the unlock, and the
//: settings markup is already parsed (app.js is held to its gzip ratchet).
markOtherDevice().catch(() => {});

function refuseOnOtherDevice(event) {
  const target = event.target instanceof Element ? event.target : null;
  const control = target?.closest("button, input, select, textarea, label, a");
  if (!control?.closest("[data-this-computer]")) return;
  if (control.closest("[data-help-for], .help-body, summary")) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  toast(THIS_COMPUTER_ONLY, "info");
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    // readAsDataURL gives "data:<type>;base64,<payload>", take the payload.
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

//: A download from a locked route. `window.open(path)` is a navigation and
//: sends no `X-Auth-Token` (only `fetch` can), so on any notebook with a
//: password it opened a tab reading "Locked: unlock first" instead of the
//: file (tests/test_locked_downloads.py). The server's own
//: `Content-Disposition` names the file when it sends one, since it knows the
//: real extension; `fallbackName` covers a route that does not.
async function downloadFromApi(path, fallbackName) {
  try {
    const response = await api(path);
    const disposition = response.headers.get("Content-Disposition") || "";
    const named = /filename="([^"]+)"/i.exec(disposition);
    await saveFile(named ? named[1] : fallbackName, await response.blob());
  } catch (error) {
    if (!error?.isLockout) toast(error.message || "Couldn't download that.", true);
  }
}

//: The browser's own download of a Blob: the one copy of the hidden-anchor
//: click (audit FE-16 found it written out in four files). `saveFile` is the
//: caller to use for an export, since it also covers the desktop window,
//: which swallows this click; this is for a file that is already in the
//: desktop's exports folder (the Settings list) or a browser-only path.
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  // In the document, not detached: some engines ignore a click on an anchor
  // that was never in the DOM.
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Save a Blob under `filename`. Resolves once the file is somewhere the user
// can find it, and says where when that isn't the browser's own downloads.
async function saveFile(filename, blob) {
  if (await desktopShell()) {
    try {
      const saved = await apiJson("/files/save", {
        method: "POST",
        body: JSON.stringify({
          filename,
          content_base64: await blobToBase64(blob),
        }),
      });
      // Where it went matters more here than in a browser: there is no
      // downloads shelf to look at, so an unannounced file is a lost one.
      // An action button on the toast itself, not just a path in the text,
      // is what makes that true rather than aspirational, asked for
      // directly after "I have to dig in the app data files to find them".
      toastAction(`Saved to ${saved.path}`, "Open folder", () => {
        apiJson("/files/open-exports-folder", { method: "POST" }).catch((error) => {
          toast(error.message || "Couldn't open the exports folder.", true);
        });
      }, { record: false });
      renderExportsList();
      //: **A saved file is a notification, not only a toast.** Asked for
      //: (INBOX 159): "exported or downloaded files and images etc should
      //: appear in the notifications to be accessible". A toast is gone in
      //: seconds and the path in it was the only record of where the file
      //: went; the notification stays, and opening it opens the folder.
      recordNotification({
        kind: "export",
        title: `Saved ${saved.filename}`,
        detail: saved.path,
        key: `export:${saved.path}`,
        action: { exports: true },
      });
      return saved;
    } catch (error) {
      toast(`Couldn't save ${filename}: ${error.message}`, true);
      return null;
    }
  }
  downloadBlob(blob, filename);
  //: UX-11: a download said nothing; Settings' list is the desktop's folder.
  toast(`Downloaded ${filename}, to your browser's downloads.`);
  //: The browser's own downloads shelf has the file; this is the record of
  //: it inside the app, so the notifications list says the same thing on a
  //: browser tab as it does on the desktop (INBOX 159).
  recordNotification({
    kind: "export",
    title: `Downloaded ${filename}`,
    detail: "In your browser's downloads folder",
    key: `download:${filename}:${Date.now()}`,
    action: { exports: true },
  });
  return { filename };
}

// --- Wave M: batch operations on notes ----------------------------------------------

let selectMode = false;
const selectedIds = new Set();

function updateBatchCount() {
  const n = selectedIds.size;
  $("batch-count").textContent = `${n} selected`;
  // The Timeline's table selects into the same set through the same actions
  // (TIMELINE_PLAN decision 6), so there are two bars showing one count.
  $("timeline-batch-count").textContent = `${n} selected`;
  //: The Select all toggles say what pressing them would do.
  const label = (rows) =>
    rows.length > 0 && rows.every((row) => selectedIds.has(row.id))
      ? "ph:x-square Select none"
      : "ph:checks Select all";
  const notesAll = $("batch-select-all");
  if (notesAll) setLabel(notesAll, label(libraryVisibleRows()));
  const timelineAll = $("timeline-batch-select-all");
  if (timelineAll) setLabel(timelineAll, label(timelineSelectableRows()));
}

// **One step, not three.** This used to be a `<select>` of categories beside
// a separate "Move" button: you picked a category, which did nothing, then
// pressed Move: and pressing Move without having picked produced an error
// toast ("Pick a category to move them to"). A menu whose items *are* the
// categories removes the second control and the failure state with it:
// choosing a category is the move. It also puts the list in the app's own
// menu styling instead of the operating system's select popup.
function fillBatchCategories(hostId = "batch-category-host") {
  const host = $(hostId);
  if (!host) return;
  //: Every category, not only those with a note on the loaded page: one
  //: made empty in Manage categories was missing from this menu (INBOX 432).
  const names = [...new Set([...categoryMeta.keys(), ...allEntries.map((e) => e.category)])].filter(Boolean).sort(compareCategoryNames);
  const items = names.map((name) =>
    makeMenuItem(`ph:folder ${name}`, `Move the selected notes to ${name}`, () =>
      batchMove(name)
    )
  );
  items.push(
    makeMenuItem("ph:plus New category…", "Move them to a category you name now", async () => {
      const category = await promptDialog("New category name:", "", { confirmLabel: "Move" });
      if (category) await batchMove(category);
    })
  );
  host.replaceChildren(labelledMenu("ph:folder-open Move to", items, "Move selected notes to a category"));
}

//: **One selection, two surfaces.** The Timeline's table ticks rows into this
//: same `selectedIds` set and runs the same `batchMove`/`batchTag`/
//: `batchDelete` (TIMELINE_PLAN decision 6: "the Notes selection bar drives
//: bulk actions"), so a note moved from the table takes exactly the path a
//: note moved from the Notes list takes, including the undo. Each surface has
//: its own bar because each lives in its own tab; both read one count and one
//: set, which is what stops the two from disagreeing.
function enterSelectMode() {
  selectMode = true;
  selectedIds.clear();
  fillBatchCategories();
  fillBatchMore();
  fillBatchCategories("timeline-batch-category-host");
  fillBatchMore("timeline-batch-more-host");
  updateBatchCount();
  show("batch-bar");
  setActiveChoice($("select-btn"), true);
  syncTimelineSelectUi();
  // The table's tick column only exists while the mode is on, so entering or
  // leaving the mode is a repaint of it. Measured the other way: after a bulk
  // action the table kept a column of boxes for a mode that had ended.
  paintTimeline();
  renderEntries();
}

function exitSelectMode() {
  selectMode = false;
  selectedIds.clear();
  hide("batch-bar");
  setActiveChoice($("select-btn"), false);
  syncTimelineSelectUi();
  paintTimeline();
  renderEntries();
}

function batchSelection() {
  const ids = [...selectedIds];
  if (!ids.length) toast("Tick some notes first.", "info");
  return ids;
}

async function batchMove(category) {
  const ids = batchSelection();
  if (!ids.length) return;
  if (!category) return;
  //: One call, with an undo that puts each note back where it was (INBOX
  //: 431 (e), `moveNotesToCategory`), where it was a PUT per note and none.
  exitSelectMode();
  await moveNotesToCategory(ids, category);
}

//: Tags for the selected notes (INBOX 447 (4)): add some, remove some, one
//: action with one Undo, in tag-manager.js (lazy). It was a prompt that
//: added one comma list a note at a time, and a second prompt to remove one
//: tag, each a PUT per note.
function batchTag() {
  const ids = batchSelection();
  if (ids.length) openBulkTags(ids);
}

//: **The rest of what one note's menu does, for many** (INBOX 432: the
//: selection bar could move, tag and delete, and nothing else). One PUT or
//: POST per note, one toast, one undo, the shape `batchTag` has.
async function batchEach(label, ids, forward, backward) {
  for (const id of ids) await forward(id);
  exitSelectMode();
  await loadEntries();
  const undo = async () => {
    for (const id of ids) await backward(id);
    await loadEntries();
  };
  const redo = async () => {
    for (const id of ids) await forward(id);
    await loadEntries();
  };
  const action = pushUndo(label, undo, redo);
  toastAction(`${label}.`, "Undo", async () => {
    settleUndoFromToast(action);
    await undo();
  });
}

function batchPut(body) {
  return (id) => apiJson(`/entries/${id}`, { method: "PUT", body: JSON.stringify(body) });
}

function batchNoun(ids) {
  return nounCount(ids.length, "note");
}

async function batchFavourite(on) {
  const ids = batchSelection().filter((id) => Boolean(allEntries.find((e) => e.id === id)?.pinned) !== on);
  if (!ids.length) return toast(on ? "They are all Favourites already." : "None of them is a Favourite.");
  await batchEach(`${on ? "Added" : "Removed"} ${batchNoun(ids)} ${on ? "to" : "from"} Favourites`, ids, batchPut({ pinned: on }), batchPut({ pinned: !on }));
}

async function batchArchive() {
  const ids = batchSelection();
  if (!ids.length) return;
  await batchEach(
    `Archived ${batchNoun(ids)}`,
    ids,
    (id) => apiJson(`/entries/${id}/archive`, { method: "POST" }),
    (id) => apiJson(`/entries/${id}/unarchive`, { method: "POST" })
  );
}

async function batchPublish() {
  const ids = batchSelection().filter((id) => allEntries.find((e) => e.id === id)?.is_draft);
  if (!ids.length) return toast("None of them is a draft.");
  await batchEach(`Published ${batchNoun(ids)}`, ids, batchPut({ is_draft: false }), batchPut({ is_draft: true }));
}

function fillBatchMore(hostId = "batch-more-host") {
  const host = $(hostId);
  if (!host || host.childElementCount) return;
  host.appendChild(
    kebabMenu(
      [
        { label: "ph:star Add to Favourites", run: () => batchFavourite(true), group: "mark" },
        { label: "ph:star-half Remove from Favourites", run: () => batchFavourite(false), group: "mark" },
        { label: "ph:paper-plane-tilt Publish drafts", run: batchPublish, group: "state" },
        { label: "ph:archive Archive", run: batchArchive, group: "state" },
        { label: "ph:stack Move to space…", run: batchMoveToSpace, group: "move" },
        { label: "ph:download-simple Export as Markdown", run: batchExport, group: "move" },
      ],
      "More for the selected notes"
    )
  );
}

//: **Export the selection** (WORLD_CLASS_PLAN 5 item 6): the Markdown zip
//: Settings' Export writes, for these notes only.
function batchExport() {
  const ids = batchSelection();
  if (!ids.length) return;
  downloadFromApi(`/export/markdown?ids=${ids.join(",")}`, `memorymap-${ids.length}-notes.zip`);
}

async function batchDelete() {
  const ids = batchSelection();
  if (!ids.length) return;
  // No confirm dialog: this is a soft delete (DELETE /entries/{id} moves a
  // note to the bin, not gone) and the toastAction below already offers a
  // one-click Undo: the single-note "Move to bin" action right above this
  // function established the same pattern (Wave J). Gating an already-
  // reversible action behind an interrupting confirm *and* an undo toast is
  // redundant friction, not extra safety (Tier 3 §30e).
  for (const id of ids) await api(`/entries/${id}`, { method: "DELETE" });
  exitSelectMode();
  await loadEntries();
  const restoreAll = async () => {
    for (const id of ids) await api(`/entries/${id}/restore`, { method: "POST" });
    await loadEntries();
  };
  const binAll = async () => {
    for (const id of ids) await api(`/entries/${id}`, { method: "DELETE" });
    await loadEntries();
  };
  const action = pushUndo(`Moved ${nounCount(ids.length, "note")} to the bin`, restoreAll, binAll);
  toastAction(`Moved ${ids.length} to the bin.`, "Undo", async () => {
    settleUndoFromToast(action);
    await restoreAll();
    toast("Notes restored.");
  });
}
