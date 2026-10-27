# voiceup-1011 (UI_MODERNISATION V1 to V8, T1, T2; Brief 96)

Done:
- Brief 96, the recording card (9adf87480): waveform, playhead, time, marks with comments.
- V1 and V2 (70f2622cc): background transcription with Stop and a notification; the recording dock; the microphone fold and Settings, Microphone.
- V3 to V7 (72fc97ee8): enhancement on save, the still meter, live words while recording, the doors to live captions, the recorder redesign.
- V8 (1a27526f8): the focus timer. T1 and T2 (2e9f2fbe3): Tidy's review pane and Recent runs.

Left:
- One commit per item was not kept for V1 with V2 and V3 to V7: a staged gate took 12 to 25 minutes under load, so items sharing meetings.js were gated together.
- The plan's Built blocks for V1 to V8, T1, T2 (UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-11 (voice notes ...)" and "(Tidy ...)") move to HISTORY at merge.

Not verified:
- Real transcription: faster-whisper is not installed; every run used a stubbed `voice.iter_segments` (vu/stubserve.py), and live words used scratchpad/fake_captions_server.py.
- Enhancement on a real voice: measured on synthetic tones through Chromium's fake microphone (RMS 0.054 to 0.082, peak 0.158 to 0.254); takes over 30 minutes are kept as recorded (decoding an hour in the page holds about 700 MB).
- A reload loses the page's watch on a running transcription; the card still reads its state from the server, but no notification fires for a run that ends after the reload.
- The chime is not heard by a sweep; only that no error is thrown.

Found, not fixed:
- The Tidy review title was 12px because `.card h3` (the eyebrow) outranked `.tidy-title`; fixed here, but other sheets' h3 titles may carry the same rank problem.
