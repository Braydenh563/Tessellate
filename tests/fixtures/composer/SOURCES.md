# Sources of the phrasing fixtures

`phrasing_1111.json` holds short single-sentence user turns, grouped by what the person wanted,
for `tests/test_phrasing_real_1111.py`. The raw data sets are not in the repo; only the
sentences below are, with names of people, places, numbers and anything identifying removed or
replaced by a general word ("my boss", "my friend").

| Set | Licence | Used for | Where from |
| --- | --- | --- | --- |
| CLINC150 (Larson et al., 2019, "An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction") | CC BY 3.0 | greeting, goodbye, thanks, joke, "what can you do", bot or human, name, employer, age; out-of-scope; reminder, to-do list and calendar updates; meeting, PTO and date questions | https://github.com/clinc/oos-eval |
| Schema-Guided Dialogue (Rastogi et al., 2020, DSTC8) | CC BY-SA 4.0 | alarm, weather and events requests (the first two user turns of single-service dialogues); its public splits hold no calendar service | https://github.com/google-research-datasets/dstc8-schema-guided-dialogue |
| WildChat 4.8M, non-toxic (Zhao et al., 2024, "WildChat: 1M ChatGPT Interaction Logs in the Wild") | ODC-BY | general-knowledge questions that are not about the notebook | https://huggingface.co/datasets/allenai/WildChat-4.8M |

How they were filtered: English; 2 to 14 words; one sentence; no digits, e-mail addresses or links;
no proper names. WildChat was sampled through the datasets server (`/rows`) for first user turns that open
with a question word; its search endpoint was down on 2026-11-11, so the sample is small.
CC BY-SA 4.0 asks that adapted material keep that licence: the SGD sentences in `phrasing_1111.json`
stay under CC BY-SA 4.0, the rest of the repository is unaffected.
