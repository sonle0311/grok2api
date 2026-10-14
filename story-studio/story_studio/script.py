"""Script budgeting and parsing. Ported from KTV gemini_service, provider calls removed."""

import json
import math
import re


def calculate_duration_metrics(duration_target: str, custom_chapters: str = "") -> dict:
    cleaned = re.sub(r"\(.*?\)", "", (duration_target or "").strip().lower()).strip()
    if cleaned in {"tự động", "auto", ""}:
        total_seconds = 60
    else:
        hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:tiếng|h(?![\wà-ỹ])|hour|gio|giờ)", cleaned)
        min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:phút|p(?![\wà-ỹ])|min|minute)", cleaned)
        sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:giây|s(?![\wà-ỹ])|sec|second)", cleaned)
        if hour_match:
            total_seconds = int(float(hour_match.group(1)) * 3600)
            if min_match:
                total_seconds += int(float(min_match.group(1)) * 60)
        elif min_match:
            total_seconds = int(float(min_match.group(1)) * 60)
            if sec_match:
                total_seconds += int(float(sec_match.group(1)))
        elif sec_match:
            total_seconds = int(float(sec_match.group(1)))
        else:
            digits = re.findall(r"\d+", cleaned)
            if not digits:
                total_seconds = 60
            else:
                number = int(digits[0])
                total_seconds = number * 60 if number <= 180 else number
    total_seconds = max(30, min(7200, total_seconds))
    total_minutes = total_seconds / 60.0
    target_words = max(90, round(total_minutes * 145))
    if total_minutes > 12:
        explicit = re.findall(r"\d+", str(custom_chapters or "").lower())
        chapters = max(2, min(30, int(explicit[0]))) if explicit else max(2, min(24, math.ceil(total_minutes / 5.2)))
        scenes = chapters * 5
        words_per_scene = max(140, round(target_words / scenes))
        multi = True
    else:
        chapters = 1
        multi = False
        if total_seconds <= 45:
            scenes = 3
        elif total_seconds <= 75:
            scenes = 5
        elif total_seconds <= 200:
            scenes = 7
        elif total_seconds <= 360:
            scenes = 9
        elif total_seconds <= 660:
            scenes = 11
        else:
            scenes = 12
        words_per_scene = max(40, round(target_words / scenes))
    return {
        "total_seconds": total_seconds,
        "total_minutes": round(total_minutes, 1),
        "target_words": target_words,
        "is_multi_chapter": multi,
        "num_chapters": chapters,
        "target_scenes": scenes,
        "words_per_scene": words_per_scene,
    }


def resolve_target_language(language: str, topic_sample: str = "") -> str:
    lang = str(language or "").strip().lower()
    named = (
        (("nhật", "japanese"), "Tiếng Nhật"),
        (("hàn", "korean"), "Tiếng Hàn"),
        (("trung", "chinese"), "Tiếng Trung"),
        (("tây ban nha", "spanish"), "Tiếng Tây Ban Nha"),
        (("anh", "english"), "Tiếng Anh"),
        (("việt", "vietnamese"), "Tiếng Việt"),
    )
    if lang in {"ja", "ko", "zh", "es", "en", "vi"}:
        return {"ja": "Tiếng Nhật", "ko": "Tiếng Hàn", "zh": "Tiếng Trung", "es": "Tiếng Tây Ban Nha", "en": "Tiếng Anh", "vi": "Tiếng Việt"}[lang]
    for keys, label in named:
        if any(key in lang for key in keys):
            return label
    if lang and "tự động" not in lang and "auto" not in lang:
        return language.strip()
    sample = str(topic_sample or "")
    if any(char.lower() == "đ" or "à" <= char.lower() <= "ỹ" for char in sample):
        return "Tiếng Việt"
    return "Tiếng Anh" if sample.split() else "Tiếng Việt"


def segment_scene_sentences(voiceover: str) -> list[dict]:
    if not voiceover or not str(voiceover).strip():
        return []
    chunks = [chunk.strip() for chunk in re.split(r"(?<=[.!?\n])\s+", str(voiceover).strip()) if chunk.strip()]
    merged = []
    buffer = ""
    for chunk in chunks:
        combined = f"{buffer} {chunk}".strip() if buffer else chunk
        if len(combined.split()) < 8:
            buffer = combined
        else:
            merged.append(combined)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]} {buffer}".strip()
        else:
            merged.append(buffer)
    beats = []
    for sentence in merged:
        if len(sentence.split()) > 26:
            parts = re.split(r"(?<=[;—])\s+", sentence)
            beats.extend(parts if len(parts) > 1 and all(len(part.split()) >= 8 for part in parts) else [sentence])
        else:
            beats.append(sentence)
    parsed = []
    for index, text in enumerate(beats, 1):
        duration = max(3.0, min(8.5, round(len(text.split()) / 2.0, 1)))
        if duration <= 3.5:
            pacing = "fast"
        elif duration >= 6.0:
            pacing = "slow"
        else:
            pacing = "standard"
        parsed.append({
            "sentence_index": index,
            "sentence_text": text,
            "word_count": len(text.split()),
            "suggested_seconds": duration,
            "pacing_type": pacing,
        })
    return parsed


def parse_raw_script(text: str, filename: str = "") -> dict:
    clean = (text or "").strip()
    title = filename.rsplit(".", 1)[0] if filename else "Dự án kịch bản"
    if not clean:
        return {"video_title": title, "scenes": [], "full_audio_transcript": ""}
    if filename.lower().endswith((".srt", ".vtt", ".ass")) or "-->" in clean[:400]:
        from story_studio.subtitles import parse_subtitle

        cues = parse_subtitle(clean, filename)
        scenes = [_scene(index, cue.get("text", ""), float(cue["duration_seconds"])) for index, cue in enumerate(cues, 1)]
        return _script(title, scenes)
    if clean[0] in "{[":
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            parsed = None
        raw_scenes = None
        if isinstance(parsed, dict):
            raw_scenes = parsed.get("scenes") or (parsed.get("data") or {}).get("scenes")
        if raw_scenes:
            scenes = []
            for index, scene in enumerate(raw_scenes, 1):
                voice = scene.get("voiceover") or scene.get("text") or scene.get("dialogue") or ""
                duration = float(scene.get("estimated_seconds") or scene.get("duration_seconds") or max(3.0, min(15.0, round(len(voice.split()) / 2.0, 1))))
                scenes.append(_scene(scene.get("scene_number", index), voice, duration, scene.get("scene_title") or f"Cảnh {index}"))
            return _script(parsed.get("video_title") or parsed.get("title") or title, scenes)
    scenes = []
    scene_number = 1
    for paragraph in [part.strip() for part in re.split(r"\n\s*\n+", clean) if part.strip()]:
        if paragraph.startswith("#") and len(paragraph.split()) < 12:
            title = paragraph.lstrip("#").strip()
            continue
        duration = max(3.0, min(15.0, round(len(paragraph.split()) / 2.0, 1)))
        scenes.append(_scene(scene_number, paragraph, duration))
        scene_number += 1
    return _script(title, scenes)


def _scene(number: int, voiceover: str, duration: float, title: str = "") -> dict:
    return {
        "scene_number": number,
        "scene_title": title or f"Cảnh {number}",
        "voiceover": voiceover,
        "estimated_seconds": round(duration, 1),
    }


def _script(title: str, scenes: list[dict]) -> dict:
    return {
        "video_title": title,
        "full_audio_transcript": " ".join(scene["voiceover"] for scene in scenes),
        "scenes": scenes,
    }
