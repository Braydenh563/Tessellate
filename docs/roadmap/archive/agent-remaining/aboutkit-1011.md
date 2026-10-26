# aboutkit, 2026-10-11

The owner: "Can you add like buttons in settings to run them in like the about page??"
(doctor, reinstall, tools, uninstall). Settings, About, one group "Maintenance".

- done: backend (core/doctor.py, core/maintenance.py, api/routes_maintenance.py), launcher marker in start.sh and start.bat, tests/test_maintenance.py
- next: the Maintenance group in frontend/index.html after #health-group; wiring in frontend/js/settings-controls.js; uninstall dialog; help (Guide topic, manual paths, README/INSTALL)
- done: the Maintenance group (index.html #maintenance-group, settings-controls.js renderMaintenance, 01-forms-settings.css, DESIGN.md row and its lint), Guide topic "maintenance", manual paths, README/INSTALL
- measured (scratchpad/ui-sweeps/maintenance.js, 1440 and 390, light and dark): group overflow 0, page overflow 0, 8 doctor rows inside the group, uninstall card fits (390: 24 to 366), phone refusal shown with all five buttons off; errors.js 0 errors at 1440/1024/820/390
- left: Restart now relaunches the app directly (/system/restart, Windows desktop only), not through start.bat, so a pending reinstall runs at the next launcher start; routing it through the launcher needs a Windows check (core/maintenance.py, routes_settings.py restart_app)
- left: pre-existing, not mine: tests/test_no_bare_fetch.py fails on documents-prose.js (one bare fetch)
