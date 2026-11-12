// assistant-avatar.js: the app's emblem as an assistant's head (INBOX 463 (2)).
//
// Lazy (app.js, `LAZY_MODULES.assistantAvatar`): only a person who sets
// Appearance, Assistant avatar to "App emblem" ever needs it. Entered through
// `assistantEmblemInto`, a `LAZY_ENTRY_POINTS` stand-in, from
// `assistantAvatar` (chat-agent.js), which hands over an empty box of the
// right size and keeps going.
//
// **The mark itself, not a copy of its pixels.** The emblem was a sketch
// drawn once into a scratch box and copied into every head, so a chat of 150
// replies did not hold 150 sketches. The tessellation mark (brief "logo",
// 2026-10-11) is a handful of SVG layers (`emblemArt`, phone-shell.js), so
// each head gets its own: 20 nodes, against Atlas's 115 a head. A head
// breathes like every emblem and is still under reduced motion or with
// Interface animations off (CSS, `.emblem-art`), and it is left out of the
// lift while the AI works (`head`). A change of accent redraws the heads
// where they stand (`renderBrandLogo` calls `repaintAssistantAvatars`).
(() => {
  function assistantEmblemInto(target, size) {
    const art = emblemArt(size, { head: true });
    //: The head's box decides its size (75% of an Atlas mark's disc).
    art.style.width = "100%";
    art.style.height = "100%";
    target.replaceChildren(art);
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { assistantEmblemInto });
})();
