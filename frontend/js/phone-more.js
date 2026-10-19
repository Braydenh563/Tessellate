// Lazily loaded (LAZY_MODULES.phoneMore in lazy-entries.js): the sheet the phone bar's
// More column opens. Boot keeps the button's listener, `PHONE_MORE_TABS` and
// the badge sync (phone-shell.js); the sheet is built here on the first press,
// which keeps it off the boot scripts' gzip budget (tests/test_boot_budget.py).
//
// **Two groups, pages first** (INBOX 1314, the owner: "the bottom nav bar just
// doesnt make sense with how it works"). Measured before: seven rows in one
// undivided list, three of them pages and four of them tools, so a row's
// press either moved you somewhere or opened something over where you were and
// nothing said which. Now the pages behind the bar (Graph, Timeline,
// Reminders) come first, a hairline, then the tools, the same `.menu-sep` a
// `kebabMenu` draws where its groups change.

function openPhoneMoreSheet() {
  const opener = document.getElementById("phone-more-btn");
  opener?.setAttribute("aria-expanded", "true");
  openSheet({
    label: "More",
    name: "more",
    returnFocus: opener,
    onClose: () => opener?.setAttribute("aria-expanded", "false"),
    build: (card, close) => {
      const list = document.createElement("div");
      list.className = "sheet-list";
      const counted = (row, count, title = "") => {
        if (!count) return row;
        const badge = document.createElement("span");
        badge.className = "tab-badge";
        badge.textContent = String(count);
        if (title) badge.title = title;
        row.appendChild(badge);
        return row;
      };
      let pages = 0;
      for (const tab of PHONE_MORE_TABS) {
        //: Simple mode (Settings, General) hides these tabs everywhere, the
        //: sheet included; the palette still opens them.
        if (document.documentElement.dataset.simple === "on") continue;
        //: Read off the tab button rather than written out again here: the
        //: icon and the caption are then the same two things the strip shows
        //: at every other width.
        const button = document.querySelector(`#tab-bar button[data-tab="${tab}"]`);
        if (!button) continue;
        const icon = button.querySelector(".tab-icon")?.className || "ph ph-circle tab-icon";
        const caption = button.querySelector(".tab-label")?.textContent?.trim()
          || button.getAttribute("aria-label") || tab;
        const row = sheetRow(icon, caption, () => {
          close();
          switchTab(tab);
        });
        //: The page you are on is marked, as the bar marks its four.
        if (button.classList.contains("active")) row.setAttribute("aria-current", "page");
        list.appendChild(counted(row, tab === "reminders" ? phoneMoreDueCount() : 0));
        pages += 1;
      }
      if (pages) {
        const rule = document.createElement("div");
        rule.className = "menu-sep";
        rule.setAttribute("role", "separator");
        list.appendChild(rule);
      }
      //: **The agent and the Guide, where the header cannot hold them**
      //: (INBOX 190): at 390 the header's first cluster with both scrolled
      //: the app sideways (407px against 390).
      list.appendChild(sheetRow("ph ph-strategy tab-icon", "Ask the agent", () => {
        close();
        toggleAgentPalette();
      }));
      //: The command palette, which a phone had no other way to open.
      list.appendChild(sheetRow("ph ph-command tab-icon", "Commands", () => {
        close();
        if (typeof openPalette === "function") openPalette();
      }));
      list.appendChild(sheetRow("ph ph-question tab-icon", "Guide", () => {
        close();
        openHelpChat();
      }));
      //: The agent's runs, which the status bar holds above 600 (INBOX 430).
      const runs = phoneMoreRunCount();
      if (runs) {
        list.appendChild(counted(sheetRow("ph ph-strategy tab-icon", "Agent activity", () => {
          close();
          $("status-activity")?.click();
        }), runs));
      }
      list.appendChild(sheetRow("ph ph-gear tab-icon", "Settings", () => {
        close();
        if (typeof openSettingsModal === "function") openSettingsModal();
      }));
      card.appendChild(list);
    },
  });
}
