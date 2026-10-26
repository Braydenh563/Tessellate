"""The recordings library (WORLD_CLASS_PLAN 28.5 row 6): a Library sub-tab
from the recipes, play at 0.5 to 2x, the saved waveform, markers while
recording (M and a button), trim into a new object, delete into the bin.
Driven by `scratchpad/ui-sweeps/audio80.js` ACT=library at 1440 and 390."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend/js/meetings.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")


def test_a_library_section_on_the_dock_recipe():
    assert 'data-target="library-view-recordings">Recordings</button>' in HTML
    section = HTML.split('id="library-view-recordings"')[1].split("</section>")[0]
    for part in ('class="dock"', "dock-identity", "dock-find", "dock-actions", 'data-help-for="recordings-help"'):
        assert part in section


def test_speeds_half_to_double():
    assert "const RECORDING_SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];" in JS


def test_markers_while_recording_by_button_and_key():
    assert 'id="meeting-marker"' in HTML
    assert "meetingTake.markers.push(at)" in JS


def test_trim_writes_a_new_wav_object_pointing_at_its_original():
    block = JS.split("async function trimRecording(")[1].split("\n}\n")[0]
    assert 'mime: "audio/wav", source_id: rec.id' in block
    assert "mp3" not in JS.lower()


def test_a_recording_is_seekable_before_its_first_seek():
    assert "audio.currentTime = 1e101;" in JS


def test_the_bin_restores_a_recording():
    lib = (ROOT / "frontend/js/library.js").read_text(encoding="utf-8")
    assert 'restore: `/recordings/${item.id}/restore`' in lib


def test_a_recording_is_a_card_with_a_playhead_and_the_time():
    """Brief 96 (INBOX 859): the head line, the player with a playhead and
    "1:12 / 4:30", a press or a drag seeks."""
    row = JS.split("function recordingRow(rec) {")[1].split("\n}\n")[0]
    for part in ('"recording-head"', '"recording-player"', '"muted recording-time"', "recordingMarksFill(li)"):
        assert part in row
    wave = JS.split("function recordingWave(rec, audio, time) {")[1].split("\n}\n")[0]
    assert "setPointerCapture" in wave and '"pointermove"' in wave
    assert "${meetingClockText(now * 1000)} / ${meetingClockText(length * 1000)}" in wave
    assert '"aria-valuetext"' in wave
    paint = JS.split("function recordingPaint(canvas, rec, played) {")[1].split("\n}\n")[0]
    assert "paint.fillStyle = ink;" in paint


def test_marks_at_the_playhead_with_a_comment_link_into_the_transcript():
    add = JS.split("async function addRecordingMark(li) {")[1].split("\n}\n")[0]
    assert "audio.currentTime * 1000" in add and "promptDialog(" in add and "pushUndo(" in add
    save = JS.split("async function saveRecordingMarks(li, marks) {")[1].split("\n}\n")[0]
    assert "{ at: m.at, note: m.note }" in save
    assert "recordingShowLine(li, ms)" in JS
    assert 'event.key.toLowerCase() !== "m"' in JS.split("function recordingRow(rec) {")[1].split("\n}\n")[0]


def test_transcription_is_a_background_run_with_stop_and_a_notification():
    """V1 (INBOX 828): "if I close it, can I leave it in running in the
    background ... can I get a notification when it is done?? also can I
    stop it". The dialog and the ⋯ start a server run and watch it; the
    ending is a notification with Open; Stop is on the card and the dialog."""
    take = JS.split("async function meetingTranscribeTake(saved, length) {")[1].split("\n}\n")[0]
    assert "startRecordingTranscription(saved" in take and "/transcribe`" not in take
    row = JS.split("async function transcribeRecording(rec) {")[1].split("\n}\n")[0]
    assert "startRecordingTranscription(rec" in row
    assert "/transcribe/start" in JS and "/transcribe/stop" in JS
    ended = JS.split("async function recordingTranscriptionEnded(rec, run, hooks) {")[1].split("\n}\n")[0]
    assert 'action: { open: "recording", id: rec.id }' in ended and "recordNotification(" in ended
    status = (ROOT / "frontend/js/notifications.js").read_text(encoding="utf-8")
    assert "recording: [(id) => apiJson(`/recordings/${id}`" in status and "openRecordings(id)" in status
    assert 'id="meeting-stop-transcribe"' in HTML


def test_a_recording_outlives_its_dialog_in_the_dock():
    close = JS.split("function closeMeetingRecorder() {")[1].split("\n}\n")[0]
    assert "meetingRecorder.stop()" not in close and "syncRecordingDock()" in close
    dock = HTML.split('id="recording-dock"')[1].split("</div>\n  </div>")[0]
    for part in ('id="recording-dock-time"', 'id="recording-dock-pause"', 'id="recording-dock-stop"', 'id="recording-dock-open"'):
        assert part in dock
    assert 'id="meeting-discard-take"' in HTML and "function discardMeetingTake()" in JS


def test_the_microphone_is_chosen_cleaned_and_tested_in_one_set_of_controls():
    """V2 (INBOX 828): "noise supression, voice enhancement, audio input
    devices and ports etc need to be managable". Every recorder asks for
    the chosen device and the three cleanups; the controls are drawn once
    into the recorder's fold and into Settings."""
    media = (ROOT / "frontend/js/media.js").read_text(encoding="utf-8")
    assert "function micAudioConstraints()" in media
    for key in ("micNoise", "micEcho", "micGain", "deviceId: { ideal: device }"):
        assert key in media
    captions = (ROOT / "frontend/js/captions.js").read_text(encoding="utf-8")
    for text in (media, JS, captions):
        assert "getUserMedia({ audio: true })" not in text
        assert "getUserMedia({ audio: micAudioConstraints() })" in text
    assert "enumerateDevices" in JS and "const MIC_TEST_MS = 3000;" in JS
    assert 'id="mic-settings-controls"' in HTML and 'id="meeting-mic-controls"' in HTML
    settings = (ROOT / "frontend/js/settings-controls.js").read_text(encoding="utf-8")
    assert 'micControlsInto($("mic-settings-controls"))' in settings


def test_enhancement_on_save_is_local_and_switchable():
    """V3: a high-pass and a loudness normalise in the page, on by default,
    a new object pointing at the original; the original goes to the bin only
    when the transcript is saved."""
    block = JS.split("async function enhanceRecording(")[1].split("\n}\n")[0]
    assert "createBiquadFilter()" in block and '"highpass"' in block
    assert 'derived: "enhanced"' in block and "source_id: rec.id" in block
    assert 'prefs.bool("micEnhance", true)' in JS
    assert "meetingAcceptOriginal()" in JS.split("async function saveVoiceNoteText(")[1].split("\n}\n")[0]
    assert 'data-mic-pref="micEnhance"' in JS or '"micEnhance"' in JS.split("const MIC_SWITCHES")[1].split(";")[0]


def test_enhancement_gain_is_bounded():
    """The normalise lifts quiet speech to about -20 dBFS RMS but never past
    -1 dBFS peak nor by more than 20 dB."""
    assert "const ENHANCE_TARGET_RMS = 0.1;" in JS
    assert "const ENHANCE_PEAK = 0.89;" in JS
    assert "const ENHANCE_MAX_GAIN = 10;" in JS


def test_level_line_is_the_signal_and_still_with_reduced_motion():
    """V4: the line draws the analyser's own samples; with reduced motion
    (the system setting or the app's) it is a static meter, a bar that steps
    four times a second instead of a line that scrolls."""
    block = JS.split("function startMeetingWave(")[1].split("\nfunction ")[0]
    assert "analyser.getByteTimeDomainData(samples)" in block
    assert "const still = reducedMotionWanted();" in block
    assert "MEETING_WAVE_STILL_EVERY" in block and "drawStill(level)" in block
    assert "const MEETING_WAVE_STILL_EVERY = 15;" in JS
    assert 'canvas.dataset.mode = still ? "meter" : "line";' in block


CAPTIONS = (ROOT / "frontend/js/captions.js").read_text(encoding="utf-8")


def test_live_words_while_recording_come_from_the_captions_pipeline():
    """V5: the recorder lends its stream to live captions, which paint into
    the dialog rather than the dock and stop without saving a note; Pause
    holds them; the full pass replaces them in review."""
    start = CAPTIONS.split("async function startLiveCaptions(")[1].split("\n}\n")[0]
    assert "opts.stream" in start and "into: opts.into" in start
    assert "if (captionRun.held) return;" in start
    release = CAPTIONS.split("function captionRelease(")[1].split("\n}\n")[0]
    assert "if (!captionRun.shared)" in release
    stop = CAPTIONS.split("async function stopLiveCaptions(")[1].split("\n}\n")[0]
    assert 'JSON.stringify({ save: false })' in stop
    assert 'id="meeting-live"' in HTML and 'aria-live="polite"' in HTML.split('id="meeting-live"')[1].split(">")[0]
    started = JS.split("function meetingRecordingStarted(")[1].split("\n}\n")[0]
    assert "meetingLiveWordsStart()" in started
    assert "stopRecorderWords()" in JS.split("async function meetingRecordingStopped(")[1].split("\n}\n")[0]
    assert "holdLiveCaptions(" in JS.split("function toggleMeetingPause(")[1].split("\n}\n")[0]


def test_live_captions_have_doors_where_people_look():
    """V6 (INBOX 828, "where is the live captions?? ... how do I use and
    access them"): a Captions button in the voice note dialog and the
    Recordings bar, the Tools and features row, the palette, and a Guide
    topic that answers the question in its own words."""
    from tessellate.ai import help_chat

    assert 'id="meeting-captions"' in HTML and 'id="recordings-captions"' in HTML
    bar = HTML.split('data-dock-name="library-recordings"')[1].split("</section>")[0]
    assert 'id="recordings-captions"' in bar
    assert '$("meeting-captions")' in JS and '$("recordings-captions")' in JS
    assert "function openLiveCaptionsFrom()" in JS
    features = (ROOT / "frontend/js/app-features.js").read_text(encoding="utf-8")
    assert 'name: "Live captions"' in features
    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "live-captions")
    assert "how do i get live captions" in topic["keywords"]
    for door in ("Library, Recordings", "Voice note", "Tools and features", "command palette"):
        assert door in topic["body"], door
    found = help_chat.topics_for("how do I get live captions")
    assert found and found[0]["id"] == "live-captions"


CSS_MEET = (ROOT / "frontend/css/meetings-lazy.css").read_text(encoding="utf-8")


def test_the_recorder_is_one_large_control_with_its_clock_and_a_device_chip():
    """V7: the name, one large record control (Stop while recording) with the
    timer large beside it, the level line, the device as a chip, Pause and
    Discard; sizes from tokens."""
    rule = CSS_MEET.split("#meeting-controls > #meeting-record {")[1].split("}")[0]
    assert "var(--control-h-lg)" in rule and "var(--radius-pill)" in rule
    assert "#meeting-overlay .meeting-timer {" in CSS_MEET
    chip = CSS_MEET.split("#meeting-mic > summary {")[1].split("}")[0]
    assert "var(--radius-md)" in chip and "var(--chip-bg)" in chip


def test_after_saving_the_dialog_shows_the_first_lines_and_open():
    """V7: a save no longer drops the dialog; it shows the transcript's first
    lines with Open (and Record another), so what was kept is seen."""
    assert 'id="meeting-done"' in HTML and 'id="meeting-done-open"' in HTML and 'id="meeting-done-again"' in HTML
    assert 'state !== "done"' in JS.split("function setMeetingState(state)")[1].split("\n}\n")[0]
    for fn in ("async function saveVoiceNoteText(", "async function meetingSaveTranscript(", "async function saveMeetingDocument("):
        assert "meetingShowSaved(" in JS.split(fn)[1].split("\n}\n")[0], fn
    shown = JS.split("function meetingShowSaved(")[1].split("\n}\n")[0]
    assert 'setMeetingState("done")' in shown and "MEETING_DONE_LINES" in shown


def test_a_long_take_says_what_a_trim_costs_before_it_is_made():
    """A trim decodes the whole recording in the page (libr-1011 row 1219): a
    take of twenty minutes or more says how much memory that is; a short one
    stays quiet."""
    assert "const RECORDING_TRIM_HEAVY_MINUTES = 20;" in JS
    assert "const RECORDING_TRIM_MB_PER_MINUTE = 12;" in JS
    sheet = JS.split("function openRecordingTrim(rec) {")[1].split("\n}\n")[0]
    assert "minutes >= RECORDING_TRIM_HEAVY_MINUTES" in sheet
    assert "Trimming opens the whole recording in this tab" in sheet
    assert "card.append(start.row, end.row, kept, ...heavy, bar);" in sheet


CSS = (ROOT / "frontend/css/meetings-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    return CSS.split(selector + " {", 1)[1].split("}", 1)[0]


def test_the_speed_opener_is_the_kebabs_height():
    """The owner, 2026-10-11: "the audio speed dropdown doesnt fit the height
    of the button next to it". Measured (rec.js, a seeded WAV): the opener
    36.9px beside the 28px kebab at 1440; after, 28 and 28 at 1440, 44 and 44
    at 390."""
    rule = _rule(".recording-act .select-shell > .select-opener")
    for part in ("height: var(--target-min)", "min-height: var(--target-min)", "padding-block: 0"):
        assert part in rule


def test_the_track_has_visible_round_corners():
    """The owner, 2026-10-11: "can this audio track have curved corners??".
    It had 2.4px of corner and a fill the card's own tint matched; now the
    recorder's corner, the track tint, and bars kept off the corners (the
    corner pixel measured transparent)."""
    rule = _rule(".recording-wave")
    assert "border-radius: var(--radius-md)" in rule and "background: var(--chip-bg)" in rule
    paint = JS.split("function recordingPaint(")[1].split("\n}\n")[0]
    assert "borderTopLeftRadius" in paint and "inset + i * bar" in paint


def test_no_recordings_is_the_empty_state_recipe():
    """The owner, 2026-10-11: "can you add like an icon or smth to this page
    so it doesnt look so empty??". DESIGN.md: icon, title, one sentence, one
    action; the action is the header's Record."""
    body = JS.split("function recordingsEmpty(")[1].split("\n}\n")[0]
    for part in ("empty-state recordings-empty", "empty-icon", "ph-microphone", "empty-title", "openVoiceNote()"):
        assert part in body
    #: The title is part of the recipe now, and only in this function: no bare grey line elsewhere.
    assert JS.count("Nothing recorded yet") == 1


def test_transcribe_is_always_in_the_menu_and_says_what_is_missing():
    """INBOX 1400 dogfood: the row was added only when `voiceStatus` (fetched by
    the recorder alone) said the add-on was there, so a library opened first
    never had it, and one with no add-on had no row to say why."""
    menu = JS.split("function recordingMenu(rec) {")[1].split("\n}\n")[0]
    assert "if (voiceStatus?.available) items.push" not in menu
    row = menu.split('makeMenuItem("ph:text-aa Transcribe"')[1].split("\n  }));")[0]
    assert '"/voice/status"' in row
    assert "voiceStatus.hint" in row


def test_the_library_search_reads_transcripts_and_shows_the_line():
    render = JS.split("async function renderRecordings() {")[1].split("\n}\n")[0]
    assert "&q=" in render
    assert "recording-match" in JS
    assert "playRecordingFrom(li, rec.match.start)" in JS
