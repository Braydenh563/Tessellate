# blindfix-1031 remaining

- done: item 2 (dashboard blank after unlock): refreshActiveTab loads the visible tab (frontend/js/app.js:1194), tests/test_dashboard_blank_after_unlock_1031.py.
- not folded: the second /help/sample-notebook per boot comes from firstStepsState being called twice (frontend/js/first-run.js:22, dashboard.js:1668), not from a double renderDashboard; different cause.
- done: item 1 (Trip plan template focus): wbApplyMapTemplate opens the centre topic (whiteboard-templates.js), wbMapShownEditing counted as typing in settings-wiring.js:742, template layout toast quiet; tests/test_map_template_focus_1031.py.
- not reproduced: "template leaves an empty Untitled map N": the tile fills the open map (boards 12 to 12, 14 to 14); the empties come from each New mind map press making a map at once (library-boards-new-map, decision in MINDMAP_PLAN).
- left (item 11, not cheap): at 390px a fresh template map frames at zoom 0.24, pills 44x11 against 24x24 handles (frontend/js/whiteboard-map.js, wbFrameMapOnOpen); on a touch screen the template does not open the editor (software keyboard would cover the map), so activeElement stays BODY there.
