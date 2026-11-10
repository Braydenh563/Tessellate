# perfset-1108 remaining

- done: P4 partly, P12 (2ea64f3f); P10 (this commit); P13 not reproduced.
- left from P4: the body is still one template of 2,700 nodes (per-pane templates would cut first-open nodes; settings-body.js), model cards 16 x 6 listeners per open (settings-models.js:327, 440), 19 fold toggle listeners (settings.js wireSettingsFolds), per-key showSettingsSection work when the match moves to another pane.
- left from P10: the background pages still run on the main thread at boot; deferring them to idle or scroll was not done (search and counts want the full list).
- P13: re-measure /timeline cold on a fresh server with a 500-note seed and 20 boards (notes-list.js is not involved; routes in src/tessellate/api).
