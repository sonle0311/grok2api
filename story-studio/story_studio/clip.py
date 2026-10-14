"""Map a beat duration onto grok2api video limits.

KTV clamped some providers to 5-10 seconds. grok2api generation accepts 1-15.
Longer narration stays a still.
"""

MAX_GENERATED_CLIP_SECONDS = 15


def plan_visual(duration_seconds: float) -> str:
    if duration_seconds > MAX_GENERATED_CLIP_SECONDS:
        return "still"
    return "clip"
