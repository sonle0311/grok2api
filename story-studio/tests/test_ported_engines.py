import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from story_studio.clip import plan_visual
from story_studio.jsonutil import extract_json
from story_studio.script import calculate_duration_metrics, parse_raw_script, segment_scene_sentences
from story_studio.subtitles import beats_from_subtitles, build_srt, build_subtitles_from_beats, parse_subtitle


def test_beat_timeline_stays_continuous():
    beats = [
        {"beat_id": "b_001", "scene_number": 1, "audio_sync": "Chào mừng các bạn đến với video hôm nay.", "actual_duration": 3.2},
        {"beat_id": "b_002", "scene_number": 2, "audio_sync": "Hãy cùng khám phá bí mật của vũ trụ.", "actual_duration": 4.1},
    ]
    subs = build_subtitles_from_beats(beats)
    assert subs[0]["start_seconds"] == 0.0
    assert subs[0]["end_seconds"] == 3.2
    assert subs[1]["start_seconds"] == 3.2
    assert round(subs[1]["end_seconds"], 1) == 7.3
    srt = build_srt(subs)
    assert "00:00:00,000 --> 00:00:03,200" in srt


def test_srt_later_cue_does_not_reset_to_zero():
    content = "1\n00:00:00,000 --> 00:00:04,000\nMo dau.\n\n2\n00:00:10,500 --> 00:00:18,000\nCau sau.\n"
    cues = parse_subtitle(content, "story.srt")
    beats = beats_from_subtitles(cues)
    assert beats[1]["t_start"] == 10.5
    assert beats[1]["t_start"] != 0
    assert beats[0]["visual_mode"] == "clip"
    assert beats[1]["visual_mode"] == "clip"


def test_long_cue_stays_still():
    content = "1\n00:00:00,000 --> 00:00:18,000\nCanh dai hon gioi han video.\n"
    beats = beats_from_subtitles(parse_subtitle(content))
    assert beats[0]["visual_mode"] == "still"
    assert plan_visual(18) == "still"
    assert plan_visual(15) == "clip"


def test_duration_budget_and_sentence_split():
    metrics = calculate_duration_metrics("6 phút")
    assert metrics["total_seconds"] == 360
    assert metrics["target_scenes"] == 9
    sentences = segment_scene_sentences("Ngan. Day la mot cau du dai de thanh mot beat hoan chinh.")
    assert sentences
    assert sentences[0]["suggested_seconds"] >= 3.0


def test_script_and_llm_json():
    script = parse_raw_script("# Song lung\n\nMot doan thám hiểm trên song lung cuoi cung truoc bao.")
    assert script["video_title"] == "Song lung"
    assert len(script["scenes"]) == 1
    parsed = extract_json('noise ```json\n{"scenes": [{"voiceover": "loi"}]}\n```')
    assert parsed["scenes"][0]["voiceover"] == "loi"
