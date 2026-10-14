"""Subtitle and beat timeline. Ported from KTV video_render_service."""

import re

from story_studio.clip import plan_visual


def format_srt_time(seconds: float) -> str:
    whole = int(seconds)
    ms = int(round((seconds - whole) * 1000))
    if ms == 1000:
        whole += 1
        ms = 0
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    return format_srt_time(seconds).replace(",", ".")


def parse_subtitle(content: str, filename: str = "") -> list[dict]:
    if filename.lower().endswith(".ass") or content.lstrip().startswith("[Script Info]"):
        return _parse_ass(content)
    clean = content.replace("\r\n", "\n").replace("\r", "\n")
    time_re = re.compile(r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3})")
    subs = []
    for index, block in enumerate(clean.strip().split("\n\n")):
        match = None
        text_parts = []
        for line in block.strip().split("\n"):
            found = time_re.search(line)
            if found:
                match = found
            elif match and line.strip() and not line.strip().isdigit():
                text_parts.append(line.strip())
        if not match:
            continue
        start = _timecode_to_seconds(match.group(1))
        end = _timecode_to_seconds(match.group(2))
        subs.append(_cue(len(subs) + 1, start, end, " ".join(text_parts)))
    return subs


def build_subtitles_from_beats(visual_beats: list[dict], merge_short: bool = True, min_duration: float = 1.5) -> list[dict]:
    raw = []
    for index, beat in enumerate(visual_beats or []):
        text = (
            beat.get("audio_sync")
            or beat.get("sentence_text")
            or beat.get("text")
            or beat.get("voiceover")
            or f"Beat {index + 1}"
        )
        duration = _positive(beat, "actual_duration", "estimated_seconds", "duration_seconds") or 4.0
        raw.append({
            "scene_number": beat.get("scene_number", beat.get("beat_id", index + 1)),
            "beat_id": beat.get("beat_id", beat.get("frame_id", index + 1)),
            "duration_seconds": duration,
            "start_seconds": _optional_float(beat.get("t_start", beat.get("start_seconds"))),
            "end_seconds": _optional_float(beat.get("t_end", beat.get("end_seconds"))),
            "text": text,
        })
    if merge_short and raw:
        merged = []
        for item in raw:
            if merged and merged[-1]["duration_seconds"] < min_duration and item["duration_seconds"] < min_duration:
                previous = merged[-1]
                if item["text"] and item["text"] != previous["text"]:
                    previous["text"] = f"{previous['text']} {item['text']}".strip()
                previous["duration_seconds"] += item["duration_seconds"]
            else:
                merged.append(dict(item))
        raw = merged
    cursor = 0.0
    use_explicit = bool(raw) and all(item["start_seconds"] is not None for item in raw)
    subtitles = []
    for index, item in enumerate(raw):
        duration = float(item["duration_seconds"])
        if use_explicit:
            start = float(item["start_seconds"])
            end = float(item["end_seconds"]) if item["end_seconds"] is not None else start + duration
            if end <= start:
                end = start + duration
            duration = max(0.1, end - start)
        else:
            start = cursor
            end = cursor + duration
            cursor = end
        subtitles.append({
            "scene_number": item.get("scene_number", index + 1),
            "beat_id": item.get("beat_id", index + 1),
            "start_seconds": round(start, 2),
            "end_seconds": round(end, 2),
            "duration_seconds": round(duration, 2),
            "text": item["text"],
            "voiceover": item["text"],
        })
    return subtitles


def build_srt(subtitles: list[dict]) -> str:
    blocks = []
    for index, sub in enumerate(subtitles, 1):
        start = format_srt_time(float(sub.get("start_seconds", 0.0)))
        end = format_srt_time(float(sub.get("end_seconds", 5.0)))
        text = sub.get("text") or sub.get("voiceover") or ""
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def build_vtt(subtitles: list[dict]) -> str:
    return "WEBVTT\n\n" + build_srt(subtitles).replace(",", ".")


def beats_from_subtitles(subtitles: list[dict]) -> list[dict]:
    """SRT cues become beats without an LLM. Timing is preserved."""
    beats = []
    for index, sub in enumerate(subtitles, 1):
        duration = float(sub["duration_seconds"])
        beats.append({
            "beat_id": f"b_{index:03d}",
            "frame_id": index,
            "scene_number": sub.get("scene_number", index),
            "audio_sync": sub.get("text") or sub.get("voiceover") or "",
            "estimated_seconds": duration,
            "start_seconds": sub["start_seconds"],
            "end_seconds": sub["end_seconds"],
            "t_start": sub["start_seconds"],
            "t_end": sub["end_seconds"],
            "visual_mode": plan_visual(duration),
        })
    return beats


def _cue(number: int, start: float, end: float, text: str) -> dict:
    return {
        "scene_number": number,
        "start_seconds": round(start, 2),
        "end_seconds": round(end, 2),
        "duration_seconds": round(max(1.0, end - start), 2),
        "text": text,
        "voiceover": text,
    }


def _timecode_to_seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def _parse_ass(content: str) -> list[dict]:
    subs = []
    in_events = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[Events]"):
            in_events = True
            continue
        if not in_events or not stripped.startswith("Dialogue:"):
            continue
        parts = stripped[9:].split(",", 9)
        if len(parts) < 10:
            continue
        text = parts[9].strip().replace("\\N", "\n").replace("\\n", "\n")
        subs.append(_cue(len(subs) + 1, _ass_to_seconds(parts[1].strip()), _ass_to_seconds(parts[2].strip()), text))
    return subs


def _ass_to_seconds(value: str) -> float:
    parts = value.split(":")
    if len(parts) != 3:
        return 0.0
    seconds, _, centiseconds = parts[2].partition(".")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(seconds) + float(centiseconds or 0) / 100


def _optional_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive(item: dict, *keys: str) -> float | None:
    for key in keys:
        if item.get(key) is None:
            continue
        try:
            value = float(item[key])
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None
