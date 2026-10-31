// popup-glyph.js: the accent glyph in every popup's head (INBOX 1478, DESIGN.md
// row "A popup's anatomy"). Lazy (`LAZY_MODULES.popupAnatomy`, with
// popup-anatomy-lazy.css), fetched with the late bundles.
//
//: **Declared where the markup is, supplied where it is built.** A head written
//: in index.html carries its own `<i class="ph ph-... pop-glyph">` (the lint in
//: tests/test_ui_recipes.py counts them). A head built in script (a sheet, a
//: picker, a statistics dialog) has none, and a table here names one from its
//: title instead of a glyph argument on 45 `openSheet` calls: one delegated
//: `focusin` (a popup takes the focus as it opens, the way panel-movable.js
//: adopts one), nothing per popup. A head whose own title already holds an icon
//: keeps it and only gains the class.
const POPUP_GLYPHS = [
  [/\bsettings?\b/i, "gear"],
  [/print|pdf/i, "printer"],
  [/colour|color|highlight/i, "palette"],
  [/categor|group|folder/i, "folders"],
  [/connect|link/i, "link"],
  [/\btags?\b/i, "tag"],
  [/manual|guide/i, "book-open"],
  [/equation/i, "function"],
  [/uninstall|delete|\bbin\b/i, "trash"],
  [/review|preview/i, "eye"],
  [/export|import|report/i, "export"],
  [/statistic/i, "chart-bar"],
  [/quick access|calculator/i, "lightning"],
  [/meeting|record/i, "microphone"],
  [/translate/i, "translate"],
  [/propert|query table|note types/i, "list-bullets"],
  [/source|attach|file/i, "paperclip"],
  [/tray|snapshot|history|earlier/i, "clock-counter-clockwise"],
  [/remind/i, "bell"],
  [/add to/i, "calendar-plus"],
  [/agent|answer|explain|suggest|tidy/i, "sparkle"],
  [/device|network/i, "devices"],
  [/map|graph|tools|board/i, "graph"],
  [/people|things|merge|split|move/i, "users-three"],
  [/model/i, "cpu"],
  [/create|new|start/i, "plus-circle"],
  [/more/i, "dots-three-circle"],
];

//: Pure, so tests/test_popup_anatomy.py runs it in node.
function popupGlyphFor(title) {
  const hit = POPUP_GLYPHS.find(([pattern]) => pattern.test(title));
  return hit ? hit[1] : "app-window";
}

function popupGlyphHead(head) {
  const title = head.querySelector(".dialog-head-title");
  if (!title || head.querySelector(".pop-glyph")) return;
  const own = title.querySelector(":scope > .ph");
  if (own) {
    own.classList.remove("ph-lead");
    own.classList.add("pop-glyph");
    return;
  }
  const icon = document.createElement("i");
  icon.className = `ph ph-${popupGlyphFor(title.textContent)} pop-glyph`;
  icon.setAttribute("aria-hidden", "true");
  title.prepend(icon);
}

document.addEventListener("focusin", (event) => {
  const host = event.target instanceof Element ? event.target.closest('dialog, [role="dialog"]') : null;
  if (host) host.querySelectorAll(".dialog-head").forEach(popupGlyphHead);
}, true);
