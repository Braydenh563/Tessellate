# blindfix-1031 remaining

- done: item 2 (dashboard blank after unlock): refreshActiveTab loads the visible tab (frontend/js/app.js:1194), tests/test_dashboard_blank_after_unlock_1031.py.
- not folded: the second /help/sample-notebook per boot comes from firstStepsState being called twice (frontend/js/first-run.js:22, dashboard.js:1668), not from a double renderDashboard; different cause.
