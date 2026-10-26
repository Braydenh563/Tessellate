"""A timestamped transcript (WORLD_CLASS 28.5 row 7): the add-on's segments
kept with their times on the recording, read back as lines that seek the
player, and written out as SRT and WebVTT.

A segment is `{"start": ms, "end": ms, "text": str, "speaker": str | None}`.
Times are whole milliseconds, the unit every other recording field uses
(`duration_ms`, `markers`). `speaker` is set only by the model's naming pass
(row 11, `ai/speakers.py`); with no model it stays None and nothing shows.
"""

from __future__ import annotations

import json

#: An hour of speech is about 700 Whisper segments; this is a ceiling a
#: bad reply cannot pass, not a length anyone reaches.
MAX_SEGMENTS = 20_000
MAX_TEXT = 2_000
MAX_SPEAKER = 40
#: Row 11: a pause this long between two segments starts a new turn.
TURN_PAUSE_MS = 1_500


def _ms(value: object) -> int:
    try:
        return max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return 0


def clean(segments: object) -> list[dict]:
    """Segments as stored: times whole, in order, end never before start,
    empty text dropped."""
    out = []
    for raw in segments if isinstance(segments, list) else []:
        if not isinstance(raw, dict):
            continue
        text = " ".join(str(raw.get("text") or "").split())[:MAX_TEXT]
        if not text:
            continue
        start = _ms(raw.get("start"))
        speaker = " ".join(str(raw.get("speaker") or "").split())[:MAX_SPEAKER] or None
        seg = {"start": start, "end": max(start, _ms(raw.get("end"))), "text": text, "speaker": speaker}
        if raw.get("paragraph"):
            seg["paragraph"] = True
        out.append(seg)
        if len(out) >= MAX_SEGMENTS:
            break
    return sorted(out, key=lambda s: s["start"])


def dumps(segments: list[dict]) -> str:
    return json.dumps(clean(segments), ensure_ascii=False)


def loads(stored: str | None) -> list[dict]:
    try:
        return clean(json.loads(stored or "[]"))
    except ValueError:
        return []


def first_match(stored: str | None, needle: str) -> dict | None:
    """The first line with the words in it, as the library shows it under a
    search: `{"start": ms, "text": line}`, or None when only the name matched."""
    low = needle.lower()
    for seg in loads(stored):
        if low in seg["text"].lower():
            return {"start": seg["start"], "text": seg["text"]}
    return None


def _stamp(ms: int, mark: str) -> str:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{mark}{millis:03d}"


def to_srt(segments: list[dict]) -> str:
    """SubRip: numbered cues, a comma before the milliseconds, the speaker
    as a "Name: " lead (SRT has no voice tag)."""
    cues = []
    for n, seg in enumerate(clean(segments), 1):
        lead = f"{seg['speaker']}: " if seg["speaker"] else ""
        cues.append(f"{n}\n{_stamp(seg['start'], ',')} --> {_stamp(seg['end'], ',')}\n{lead}{seg['text']}\n")
    return "\n".join(cues)


def _vtt_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_vtt(segments: list[dict]) -> str:
    """WebVTT: the header, a full stop before the milliseconds, the speaker
    as the format's own voice tag (`<v Sam>`)."""
    cues = ["WEBVTT\n"]
    for seg in clean(segments):
        lead = f"<v {_vtt_text(seg['speaker'])}>" if seg["speaker"] else ""
        cues.append(f"{_stamp(seg['start'], '.')} --> {_stamp(seg['end'], '.')}\n{lead}{_vtt_text(seg['text'])}\n")
    return "\n".join(cues)


def turns(segments: list[dict]) -> list[list[int]]:
    """Row 11's turn-taking pass, by timing alone: a pause over 1.5 s, or a
    segment the transcriber began as a new paragraph, starts a new turn.
    The indices of each turn's segments, in order."""
    groups: list[list[int]] = []
    last_end = None
    for index, seg in enumerate(segments):
        pause = last_end is not None and seg["start"] - last_end > TURN_PAUSE_MS
        if not groups or pause or seg.get("paragraph"):
            groups.append([])
        groups[-1].append(index)
        last_end = seg["end"]
    return groups


def marks_of(recording) -> list[dict]:  # noqa: ANN001
    """A recording's marks as `{at, note}`; old takes stored bare seconds."""
    out = []
    for value in json.loads(recording.markers or "[]"):
        if isinstance(value, dict):
            out.append({"at": int(value.get("at", 0)), "note": str(value.get("note", ""))})
        elif isinstance(value, (int, float)):
            out.append({"at": int(value), "note": ""})
    return out
