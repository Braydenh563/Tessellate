// icon-picker-icons.js: the Icons tab's groups, split from icon-picker.js (L624). Loaded with it
// (`iconPicker` in LAZY_MODULES), after it; the picker reaches this through `openIconPicker.iconGroups`.
(() => {
  //: **Phosphor's groups, by what a name says** (the font carries no
  //: categories). First match wins; the rest are "More icons". Ordered so the
  //: groups a map or a note reaches for most come first.
  const ICON_PH_GROUPS = [
    ["marks", "Marks and shapes", /^(check|x-|x$|warning|question|info|seal|star|heart|flag|target|circle|square|diamond|triangle|hexagon|octagon|plus|minus|asterisk|crown|medal|trophy|lightbulb|sparkle)/],
    ["arrows", "Arrows", /^(arrow|caret|arrows|trend)/],
    ["people", "People", /(user|person|users|baby|hand|smiley|identification|student|chalkboard-teacher|detective)/],
    ["work", "Work and writing", /(file|folder|note|notebook|book|pen|pencil|paper|clipboard|article|text-|list|quotes|briefcase|kanban|calendar|clock|timer|hourglass|alarm|chart|graph|table|database|presentation|funnel|tag)/],
    ["talk", "Talk and media", /(chat|envelope|phone|bell|megaphone|paper-plane|broadcast|microphone|speaker|music|headphones|camera|video|film|image|play|pause|television)/],
    ["places", "Places and travel", /(map|globe|house|building|airplane|car|bus|train|bicycle|compass|navigation|signpost|tent|mountains|island|bridge|storefront|bank|hospital|church|school)/],
    ["nature", "Nature", /(tree|leaf|flower|plant|sun|moon|cloud|snow|drop|fire|flame|lightning|mountain|bug|cat|dog|fish|bird|paw|butterfly|cactus|plant|wave|rainbow|thermometer|wind)/],
    ["things", "Things and tools", /(key|lock|gear|wrench|hammer|gift|desktop|laptop|device|cpu|robot|rocket|lamp|coffee|cooking|fork|bag|basket|shopping|money|coin|credit|wallet|puzzle|game|dice|palette|paint|scissors|magnifying|binoculars|flask|atom|dna|pill|first-aid)/],
  ];

  //: The vendored font's glyph names, off its own stylesheet's rules.
  function iconPickerPhosphorNames() {
    const names = [];
    for (const sheet of document.styleSheets) {
      if (!/\/vendor\/phosphor\//.test(sheet.href || "")) continue;
      let rules;
      try {
        rules = sheet.cssRules;
      } catch {
        continue;
      }
      for (const rule of rules) {
        const match = /^\.ph\.ph-([a-z0-9-]+)::?before$/.exec(rule.selectorText || "");
        if (match) names.push(match[1]);
      }
    }
    return names;
  }

  function iconGroups(state) {
    if (!state.phGroups) {
      const groups = ICON_PH_GROUPS.map(([key, label]) => ({ key, label, items: [] }));
      const more = { key: "more", label: "More icons", items: [] };
      for (const name of iconPickerPhosphorNames()) {
        const at = ICON_PH_GROUPS.findIndex(([, , re]) => re.test(name));
        (at === -1 ? more : groups[at]).items.push({ kind: "icon", value: name, name: name.replace(/-/g, " ") });
      }
      state.phGroups = [...groups.filter((g) => g.items.length), ...(more.items.length ? [more] : [])];
    }
    return state.phGroups;
  }

  openIconPicker.iconGroups = iconGroups;
})();
