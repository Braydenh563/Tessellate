// model-chosen.js: the start-up choice, said once (L671, the owner 2026-10-07:
// "Say once what was chosen and why"). Lazy: only a launch that had to choose
// a chat model loads it. One line names the chat, background and picture
// models and why, with Change; once per chosen model in this browser.
settingsReadouts.chosen = (s) => {
  const key = `chatModelChosen:${s.chat_model}`;
  if (prefs.get(key) || !prefs.set(key, "1")) return;
  const bg = s.utility_model_resolved || "the chat model";
  const img = s.vision_model_resolved || "none installed";
  toastAction(
    `${aiNameNow()} now runs ${s.chat_model}: ${s.chat_model_chosen_why}. Background jobs use ${bg}; pictures use ${img}.`,
    "Change",
    () => openSettingsModal("models", "chat-model-select"),
  );
};
